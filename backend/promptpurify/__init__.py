"""
promptpurify — Python port of SecureLayer7's PROMPTPurify L5e model.

This module provides an ML-based prompt injection classifier that loads
the L5e ONNX model (ELECTRA-small, self-pretrained, ~14 MB) and runs
inference entirely in-process with onnxruntime — no Node.js dependency.

The L5e model uses a self-pretrained ELECTRA-small backbone (~13.7M params)
fine-tuned on a seeded leakage-free injection corpus. It achieves
83.94% recall at 10.61% FPR on adversarial benchmarks.

Architecture:
    User input -> L5eWordPieceTokenizer -> [CLS] [UNTRUSTED] tokens [SEP] [PAD]...
    -> ONNX session.run() -> softmax(logits) -> P(injection)

The model catches novel/creative attacks that regex-based guards miss.
"""

__all__ = ["L5eRunner", "L5eUnavailableError"]


def __getattr__(name):
    """Lazy-import L5eRunner / L5eUnavailableError to avoid triggering
    numpy/onnxruntime on package import (needed by the model downloader)."""
    if name == "L5eRunner":
        from backend.promptpurify.l5e_runner import L5eRunner
        return L5eRunner
    if name == "L5eUnavailableError":
        from backend.promptpurify.l5e_runner import L5eUnavailableError
        return L5eUnavailableError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
