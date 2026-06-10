"""
L5eRunner: Python port of PROMPTPurify's L5e ML classifier.

Faithfully replicates the TypeScript implementation from
src/l5/l5e.ts — same tokenizer algorithm, same sliding-window
inference strategy, same contract-driven configuration.

Contract: 2-input ONNX (input_ids, attention_mask) — ELECTRA
has NO token_type_ids. Tokenizer = our WordPiece vocab (cased,
do_lower_case=false). The [UNTRUSTED] trust-frame marker token
is prepended after [CLS] (prefix_token_ids = [32000]).

The model is PROBABILISTIC — it returns a score in [0, 1], not
a boolean. It is advisory only and should be combined with
deterministic regex guards.
"""

import json
import logging
import math
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class L5eUnavailableError(Exception):
    """Raised when onnxruntime or the model artifact is unavailable."""

    pass


# ──────────────────────────────────────────────────────────────────────
#  WordPiece Tokenizer (faithful port of TypeScript basicTokenize + wordpiece)
# ──────────────────────────────────────────────────────────────────────


def _is_whitespace(c: str) -> bool:
    """Check if character is whitespace (including Unicode)."""
    return c in (" ", "\t", "\n", "\r") or bool(re.fullmatch(r"\s", c))


def _is_control(c: str) -> bool:
    """Check if character is a control character (but NOT tab/newline/CR)."""
    if c in ("\t", "\n", "\r"):
        return False
    cp = ord(c)
    return (cp < 0x20 and cp != 0) or cp == 0x7F


def _is_punct(c: str) -> bool:
    """Check if character is ASCII punctuation or Unicode P/S category."""
    cp = ord(c)
    # ASCII punctuation ranges (matching JS: 33-47, 58-64, 91-96, 123-126)
    if (33 <= cp <= 47) or (58 <= cp <= 64) or (91 <= cp <= 96) or (123 <= cp <= 126):
        return True
    # Unicode punctuation (P*) and symbols (S*) via unicodedata.category
    cat = unicodedata.category(c)
    return cat.startswith("P") or cat.startswith("S")


def _is_cjk(cp: int) -> bool:
    """Check if codepoint is in CJK ranges (split into single chars)."""
    return (
        (0x4E00 <= cp <= 0x9FFF)
        or (0x3400 <= cp <= 0x4DBF)
        or (0x20000 <= cp <= 0x2A6DF)
        or (0x2A700 <= cp <= 0x2B73F)
        or (0x2B740 <= cp <= 0x2B81F)
        or (0x2B820 <= cp <= 0x2CEAF)
        or (0xF900 <= cp <= 0xFAFF)
        or (0x2F800 <= cp <= 0x2FA1F)
    )


def _strip_accents(s: str) -> str:
    """Remove combining diacritical marks (NFD decomposition)."""
    import unicodedata

    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _basic_tokenize(text: str, lower: bool) -> list[str]:
    """
    BERT BasicTokenizer: clean control chars + CJK spacing + punctuation split.

    This is a faithful port of the TypeScript `basicTokenize()` from
    PROMPTPurify's src/l5/l5e.ts. Handles:
      - Control character removal (except tab/newline/CR → space)
      - CJK character spacing (inserted as standalone tokens)
      - Lowercase + accent strip (only when lower=True)
      - Punctuation splitting (ASCII + Unicode P/S)
    """
    # Step 1: clean control chars, replace whitespace with space
    cleaned: list[str] = []
    for ch in text:
        cp = ord(ch)
        if cp == 0 or cp == 0xFFFD or _is_control(ch):
            continue
        cleaned.append(" " if _is_whitespace(ch) else ch)

    # Step 2: pad CJK chars with spaces so they become standalone tokens
    spaced: list[str] = []
    for ch in cleaned:
        cp = ord(ch)
        if _is_cjk(cp):
            spaced.extend([" ", ch, " "])
        else:
            spaced.append(ch)

    joined = "".join(spaced)

    # Step 3: split on whitespace, handle punctuation
    out: list[str] = []
    for tok in joined.split():
        if not tok:
            continue
        if lower:
            tok = _strip_accents(tok.lower())

        buf: list[str] = []
        for ch in tok:
            if _is_punct(ch):
                if buf:
                    out.append("".join(buf))
                    buf = []
                out.append(ch)
            else:
                buf.append(ch)
        if buf:
            out.append("".join(buf))

    return out


def _wordpiece(token: str, vocab: dict[str, int], unk_id: int) -> list[int]:
    """
    Greedy longest-match WordPiece tokenization.

    Starts at the end of the token and works backward, finding the longest
    prefix that exists in vocab. For subword pieces (not the first), prepends
    '##'. Falls back to [UNK] if token > 100 chars or no match found.

    This is a faithful port of the TypeScript `wordpiece()` from
    PROMPTPurify's src/l5/l5e.ts.
    """
    if len(token) > 100:
        return [unk_id]

    chars = list(token)
    sub: list[int] = []
    start = 0

    while start < len(chars):
        end = len(chars)
        cur = -1
        while start < end:
            piece = "".join(chars[start:end])
            if start > 0:
                piece = "##" + piece
            cur = vocab.get(piece, -1)
            if cur != -1:
                break
            end -= 1

        if cur == -1:
            # Unknown — whole word → UNK
            return [unk_id]

        sub.append(cur)
        start = end

    return sub


class L5eWordPieceTokenizer:
    """
    BERT-style WordPiece tokenizer using PROMPTPurify's 32k vocab.

    The tokenizer is CA S E D (do_lower_case=false per contract).
    Supports the [UNTRUSTED] trust-frame marker via prefix_token_ids.

    encode() returns (input_ids, attention_mask) ready for ONNX.
    """

    def __init__(
        self, vocab: dict[str, int], contract: dict[str, Any], max_len: int = 128
    ):
        self.vocab = vocab
        self.max_len = contract.get("max_len", max_len)
        self.do_lower_case = contract.get("do_lower_case", False)
        self.cls_id = contract.get("cls_id", 2)
        self.sep_id = contract.get("sep_id", 3)
        self.pad_id = contract.get("pad_id", 0)
        self.unk_id = contract.get("unk_id", 1)
        self.prefix_token_ids: list[int] = contract.get("prefix_token_ids", [])

    @classmethod
    def from_vocab_file(cls, vocab_path: str, contract: dict[str, Any]) -> "L5eWordPieceTokenizer":
        """Load vocab from a text file (one token per line)."""
        vocab: dict[str, int] = {}
        with open(vocab_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                vocab[line.rstrip("\n")] = i
        return cls(vocab, contract)

    def encode(self, text: str) -> tuple[list[int], list[int]]:
        """
        Tokenize text into input_ids and attention_mask.

        Layout: [CLS] [prefix_tokens...] [wordpiece tokens...] [SEP] [PAD...]

        Returns:
            (input_ids, attention_mask) — both length == max_len
        """
        prefix = self.prefix_token_ids
        reserved = 2 + len(prefix)  # [CLS] + prefix + [SEP]

        # Encode body
        body: list[int] = []
        for word in _basic_tokenize(text, self.do_lower_case):
            for wid in _wordpiece(word, self.vocab, self.unk_id):
                body.append(wid)
                if len(body) >= self.max_len - reserved:
                    break
            if len(body) >= self.max_len - reserved:
                break

        trimmed = body[: self.max_len - reserved]

        # Build final sequence
        ids = [self.cls_id] + prefix + trimmed + [self.sep_id]
        mask = [1] * len(ids)

        # Pad to max_len
        while len(ids) < self.max_len:
            ids.append(self.pad_id)
            mask.append(0)

        return ids, mask


# ──────────────────────────────────────────────────────────────────────
#  L5eRunner — ONNX inference wrapper
# ──────────────────────────────────────────────────────────────────────


class L5eRunner:
    """
    L5e ML-based prompt injection classifier.

    Loads the INT8-quantized ONNX model and WordPiece vocabulary,
    runs inference with sliding-window coverage for long prompts.

    Usage:
        runner = L5eRunner(model_dir="/path/to/models")
        score = runner.score("user input text")  # 0.0 = benign, 1.0 = injection

    The model is probabilistic — returns a float in [0, 1], not a boolean.
    Combine with deterministic guards for production use.
    """

    # Sliding window parameters (matches TypeScript L5e)
    WINDOW_CHARS = 500
    STRIDE_CHARS = 250

    def __init__(self, model_dir: str | None = None):
        """
        Initialize the L5e runner.

        Args:
            model_dir: Path to directory containing l5e.json, model.int8.onnx,
                       and vocab.txt. Defaults to the bundled models directory.

        Raises:
            L5eUnavailableError: If model artifacts or onnxruntime are missing.
        """
        if model_dir is None:
            model_dir = str(Path(__file__).resolve().parent)

        self._model_dir = model_dir
        self._contract = self._load_contract()
        self._tokenizer = L5eWordPieceTokenizer.from_vocab_file(
            os.path.join(model_dir, "vocab.txt"), self._contract
        )
        self._session = self._load_onnx_session()

    # ── helpers ────────────────────────────────────────────────────────

    def _load_contract(self) -> dict[str, Any]:
        """Load the L5e contract JSON."""
        contract_path = os.path.join(self._model_dir, "l5e.json")
        if not os.path.exists(contract_path):
            raise L5eUnavailableError(
                f"L5e contract not found at {contract_path}"
            )
        with open(contract_path, "r") as f:
            return json.load(f)

    def _load_onnx_session(self) -> Any:
        """Load the ONNX inference session (lazy import onnxruntime)."""
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise L5eUnavailableError(
                "onnxruntime not installed. Install with: pip install onnxruntime"
            ) from e

        model_path = os.path.join(
            self._model_dir, self._contract.get("model_file", "model.int8.onnx")
        )
        if not os.path.exists(model_path):
            raise L5eUnavailableError(f"ONNX model not found at {model_path}")

        try:
            session = ort.InferenceSession(
                model_path, providers=ort.get_available_providers()
            )
            logger.info(
                "L5e ONNX session loaded (providers: %s)",
                session.get_providers(),
            )
            return session
        except Exception as e:
            raise L5eUnavailableError(
                f"Failed to load L5e ONNX session from {model_path}"
            ) from e

    # ── inference ──────────────────────────────────────────────────────

    def _score_window(self, text: str) -> float:
        """
        Run ONNX inference on a single window of text.

        Returns:
            P(injection) in [0, 1]
        """
        ids, mask = self._tokenizer.encode(text)
        n = len(ids)

        # ONNX expects int64 tensors with shape [batch=1, seq_len]
        input_ids = np.array([ids], dtype=np.int64)
        attention_mask = np.array([mask], dtype=np.int64)

        feeds = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }

        output_name = self._contract["output"]  # "logits"
        out = self._session.run([output_name], feeds)
        logits = out[0]  # shape: [1, 2]

        a = float(logits[0, 0])
        b = float(logits[0, 1])

        # Softmax over 2 logits
        m = max(a, b)
        ea = math.exp(a - m)
        eb = math.exp(b - m)
        probs = [ea / (ea + eb), eb / (ea + eb)]

        inj_idx = self._contract.get("injection_logit_index", 1)
        return probs[inj_idx]

    def score(self, text: str) -> float:
        """
        Score text for prompt injection probability.

        Uses sliding-window coverage for texts longer than WINDOW_CHARS
        (same strategy as TypeScript L5e). Each window is scored
        independently and the maximum score is returned.

        Args:
            text: The user input to classify.

        Returns:
            Float in [0, 1] where higher = more likely injection.
        """
        if not text.strip():
            return 0.0

        if len(text) <= self.WINDOW_CHARS:
            return self._score_window(text)

        # Sliding window across full text (closes gap on buried-tail attacks)
        windows: list[str] = []
        start = 0
        while start + self.WINDOW_CHARS <= len(text):
            windows.append(text[start : start + self.WINDOW_CHARS])
            start += self.STRIDE_CHARS

        # Ensure last portion is covered
        if not windows or (
            windows and len(windows[-1]) < self.WINDOW_CHARS
        ):
            windows.append(text[-self.WINDOW_CHARS :])

        scores = [self._score_window(w) for w in windows]
        return max(scores) if scores else 0.0

    @property
    def version(self) -> str:
        """Model version from contract."""
        return self._contract.get("version", "unknown")

    @property
    def model_dir(self) -> str:
        """Path to model artifact directory."""
        return self._model_dir
