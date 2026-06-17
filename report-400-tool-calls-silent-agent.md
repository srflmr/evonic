# Report: Agent Becomes Unresponsive After 400 "insufficient tool messages" Error

**Date:** 2026-06-17  
**Author:** Linus (Robin Syihab's agent)  
**Status:** Root-cause analysis complete, fix plan ready for execution

---

## 1. Summary

When the LLM API returns a **400 error** with the message:

> *"An assistant message with 'tool_calls' must be followed by tool messages responding to each 'tool_call_id'."*

…the agent becomes completely silent and never responds to any subsequent user input. The user sees no reply, no error message, and no feedback — the agent simply hangs until `max_llm_calls` is exhausted, at which point it exits the turn loop without producing a visible response.

This report documents the root cause, a detailed breakdown of four interconnected problems, and a fix plan with concrete code changes.

---

## 2. Error Flow — How It Happens

1. The LLM returns an **assistant message with `tool_calls`** (e.g. calling a tool like `read_file`).
2. Before the agent can execute those tools and append matching `tool` (role) responses, something corrupts the messages array — most commonly **history truncation during summarization** (see `backend/agent_runtime/chatlog.py`, lines 339–387).
3. The corrupted messages array now contains an `assistant(tool_calls)` message **without** its required `tool` response messages.
4. On the next turn, when the messages array is sent to the LLM API, the provider rejects it with a **400 "insufficient tool messages"** error.
5. The error is classified as `api_error` by `backend/agent_runtime/llm_client.py` (lines 606–619).
6. **This error has no recovery handler** in `llm_loop.py`. The error falls through all existing handlers, and the loop eventually hits `max_llm_calls` and exits.
7. No `final_answer` event is emitted in the error path, so the frontend shows nothing.
8. The user never sees any response.

---

## 3. Root Cause Breakdown

### Problem 1: `api_error` Has No Recovery in `llm_loop.py`

**File:** `backend/agent_runtime/llm_loop.py`, lines 615–843

The error handling block in the LLM loop explicitly handles these error types:

| Error Type | Handler | Action |
|---|---|---|
| `tool_call_json_error` | Line 624 | Retry with correction message |
| `provider_error` | Line 650 | Retry with exponential backoff |
| `connection_error` | Line 650 | Retry with exponential backoff |
| `request_timeout` | Line 676 | Retry with continue prompt |
| `generation_timeout` | Line 676 | Retry with continue prompt |
| `llm_error` | Line 722 | Single retry |
| `unknown_error` | Line 722 | Single retry |
| **`api_error`** | **—** | **NO HANDLER** |

When `api_error` is encountered, it falls through all handlers:

1. If **no fallback model** is configured → returns raw error immediately.
2. If **fallback model is configured** → tries fallback → if that also fails → returns error.
3. The corrupted messages array is **never repaired**, so the same error repeats on every subsequent turn until `max_llm_calls` is exhausted.

### Problem 2: Missing `final_answer` Event in Error Path

**File:** `backend/agent_runtime/llm_loop.py`, lines 948–972

The error return path at lines 948–972 returns:

```python
return {"text": error_msg, "error": True}
```

…but does **NOT** emit a `final_answer` event. Compare with other exit paths:

| Exit Path | `final_answer` emitted? |
|---|---|
| Success (line 1237) | ✓ Yes |
| Duplicate hard-stop (line 1273) | ✓ Yes |
| Stop injection (line 610) | ✓ Yes |
| **Error path (line 948–972)** | **✗ No** |

The `turn_complete` event is still emitted by `runtime.py` (line 2016), but without `final_answer`, the frontend may not render any response text properly.

### Problem 3: `_humanize_llm_error` Returns Raw Error String

**File:** `backend/agent_runtime/llm_response_parser.py`, lines 17–59

The function `_humanize_llm_error` maps specific error patterns to user-friendly messages. However, there is **no rule** for the "insufficient tool messages" error pattern. As a result, the raw, verbose API error string (200+ characters, often containing JSON fragments) is sent directly to the user, even when it does reach the frontend.

### Problem 4: No Mechanism to Clean Up Corrupted Messages

When a 400 error occurs because the messages array contains orphaned `assistant(tool_calls)` entries (i.e., tool_calls without matching tool responses), there is **no mechanism** to detect and remove these problematic entries. The same corrupted messages persist in the array and cause the same error on the next API call, creating an infinite loop of failures.

---

## 4. Fix Plan

### Fix 1: Add Recovery Handler for `api_error` — "insufficient tool messages"

**File:** `backend/agent_runtime/llm_loop.py`

Add a new error handler block for `api_error` in the error handling section (after the existing handlers, before the fallback logic). The handler will:

1. Detect the error type by checking if the error detail contains `tool_calls`, `insufficient tool messages`, or `tool_call_id`.
2. Scan the messages array backwards for the last `assistant` message with `tool_calls`.
3. Remove that orphaned message if found — this is safe because if there were valid tool responses, the API wouldn't have returned a 400.
4. Log a warning with the index of the removed message.
5. Retry the LLM call with the cleaned-up messages array (up to `max_timeout_retries`).

**Proposed code structure (conceptual):**

```python
if error_type == 'api_error':
    _err_detail_lower = (result.get('error_detail') or '').lower()
    if ('tool_calls' in _err_detail_lower or
        'insufficient tool messages' in _err_detail_lower or
        'tool_call_id' in _err_detail_lower):
        if timeout_retries < max_timeout_retries:
            timeout_retries += 1
            # Remove orphaned assistant(tool_calls) message
            for idx in range(len(messages) - 1, -1, -1):
                if messages[idx].get('tool_calls'):
                    messages.pop(idx)
                    break
            event_stream.emit('llm_retry', {...})
            continue  # Retry the loop
```

### Fix 2: Emit `final_answer` in Error Path

**File:** `backend/agent_runtime/llm_loop.py`

In the error return path (around lines 948–972), add a `final_answer` emission before returning the error response:

```python
event_stream.emit('final_answer', {
    'agent_id': agent_id,
    'session_id': session_id,
    'external_user_id': external_user_id,
    'text': error_msg,
    'error': True,
})
```

### Fix 3: Humanize "insufficient tool messages" Error

**File:** `backend/agent_runtime/llm_response_parser.py`

Add a new pattern in `_humanize_llm_error` to detect "insufficient tool messages" and map it to a clean, user-friendly message:

```python
if 'tool_calls' in error_str or 'insufficient tool messages' in error_str:
    return (
        "The conversation history became corrupted — a tool call was missing its results. "
        "The issue has been automatically corrected. Please try your request again."
    )
```

### Fix 4: Add Unit Test for Recovery Flow

Add a unit test that:

1. Constructs a messages array with an orphaned `assistant(tool_calls)` message.
2. Mocks the LLM API to return a 400 "insufficient tool messages" error.
3. Verifies that the cleanup logic removes the orphaned message.
4. Verifies that the retry succeeds with the cleaned-up messages.

---

## 5. Files Affected

| File | Change |
|---|---|
| `backend/agent_runtime/llm_loop.py` | Add `api_error` recovery handler (Fix 1) + emit `final_answer` in error path (Fix 2) |
| `backend/agent_runtime/llm_response_parser.py` | Add humanization rule for insufficient tool messages (Fix 3) |
| Tests (TBD) | Add unit test for recovery flow (Fix 4) |

---

## 6. Risk Assessment

- **Fix 1 (Cleanup + Retry):** Low risk. The cleanup only removes an `assistant(tool_calls)` message when the API explicitly says it has no matching tool responses — this is a safe, targeted removal.
- **Fix 2 (final_answer):** Very low risk. Adding a `final_answer` emission is purely additive and does not change existing behavior.
- **Fix 3 (Humanization):** Very low risk. Only adds a new pattern match; the existing fallthrough (return raw string) is preserved for unmatched errors.
- **Fix 4 (Tests):** No production risk. Only adds test coverage.

---

## 7. Next Steps

1. Execute Fixes 1–3 in the codebase.
2. Write and run the unit test (Fix 4).
3. Perform a manual integration test by triggering the error condition and verifying the agent recovers.
4. Once validated, merge the changes into the main branch.

---

*— Robin Syihab's agent.*
