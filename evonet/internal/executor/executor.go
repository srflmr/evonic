// Package executor handles JSON-RPC method dispatch for Evonet.
package executor

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// cacheTTL is how long a completed request's result is retained for idempotent
// replay. The Evonic server only re-sends a request id within its disconnect
// grace window (currently 90s), so a few minutes is comfortably safe.
const cacheTTL = 5 * time.Minute

// inflight tracks a request that is either still executing or recently completed.
// done is closed once resp is populated; concurrent callers with the same id wait
// on done and then read resp (exactly-once execution).
type inflight struct {
	done chan struct{}
	resp Response
}

// Request is an inbound JSON-RPC command from the Evonic server.
type Request struct {
	ID     string          `json:"id"`
	Method string          `json:"method"`
	Params json.RawMessage `json:"params"`
}

// Response is the reply sent back to Evonic.
type Response struct {
	ID     string `json:"id"`
	OK     bool   `json:"ok"`
	Result any    `json:"result,omitempty"`
	Error  string `json:"error,omitempty"`
}

// Executor dispatches incoming requests to method handlers.
type Executor struct {
	workDir string
	verbose bool

	mu    sync.Mutex
	cache map[string]*inflight // req.ID → in-flight/completed result
}

func New(workDir string, verbose bool) *Executor {
	// Normalize: clean, ensure trailing separator, reject root and empty.
	clean := filepath.Clean(workDir)
	if clean == "/" || clean == "." || clean == "" {
		panic("evonet: workDir must not be root, empty, or current directory")
	}
	if !strings.HasSuffix(clean, string(os.PathSeparator)) {
		clean += string(os.PathSeparator)
	}
	return &Executor{workDir: clean, verbose: verbose, cache: make(map[string]*inflight)}
}

// Handle processes a Request and returns a Response.
//
// It guarantees exactly-once execution per request id: if the same id is seen
// again while still running, the second caller waits for and returns the first
// result; if it already completed (within cacheTTL), the cached result is
// replayed without re-executing. This lets the Evonic server safely re-send a
// request after a WebSocket reconnect without risking duplicate side effects.
func (e *Executor) Handle(req Request) Response {
	// Requests without an id can't be deduplicated — dispatch directly.
	if req.ID == "" {
		return e.dispatch(req)
	}

	e.mu.Lock()
	if existing, ok := e.cache[req.ID]; ok {
		e.mu.Unlock()
		<-existing.done // attach to in-flight or already-completed execution
		return existing.resp
	}
	entry := &inflight{done: make(chan struct{})}
	e.cache[req.ID] = entry
	e.mu.Unlock()

	entry.resp = e.dispatch(req)
	close(entry.done)
	e.scheduleEvict(req.ID)
	return entry.resp
}

// scheduleEvict removes a cached result after cacheTTL so memory stays bounded.
func (e *Executor) scheduleEvict(id string) {
	time.AfterFunc(cacheTTL, func() {
		e.mu.Lock()
		delete(e.cache, id)
		e.mu.Unlock()
	})
}

// dispatch routes a request to its method handler.
func (e *Executor) dispatch(req Request) Response {
	if e.verbose {
		e.logRequest(req)
	}
	start := time.Now()

	var resp Response
	switch req.Method {
	case "exec_bash":
		resp = e.handleExecBash(req)
	case "exec_python":
		resp = e.handleExecPython(req)
	case "read_file":
		resp = e.handleReadFile(req)
	case "write_file":
		resp = e.handleWriteFile(req)
	case "read_file_b64":
		resp = e.handleReadFileB64(req)
	case "write_file_b64":
		resp = e.handleWriteFileB64(req)
	default:
		resp = Response{ID: req.ID, OK: false, Error: fmt.Sprintf("unknown method: %s", req.Method)}
	}

	if e.verbose {
		e.logResponse(req.Method, resp, time.Since(start))
	}
	return resp
}

func (e *Executor) logRequest(req Request) {
	switch req.Method {
	case "exec_bash":
		var p execBashParams
		json.Unmarshal(req.Params, &p) //nolint
		log.Printf("[evonet] → exec_bash\n%s", scriptSnippet(p.Script))
	case "exec_python":
		var p execPythonParams
		json.Unmarshal(req.Params, &p) //nolint
		log.Printf("[evonet] → exec_python\n%s", scriptSnippet(p.Code))
	case "read_file":
		var p readFileParams
		json.Unmarshal(req.Params, &p) //nolint
		log.Printf("[evonet] → read_file: %s", p.Path)
	case "write_file":
		var p writeFileParams
		json.Unmarshal(req.Params, &p) //nolint
		log.Printf("[evonet] → write_file: %s (%s, %d bytes)", p.Path, p.Mode, len(p.Content))
	case "read_file_b64":
		var p readFileB64Params
		json.Unmarshal(req.Params, &p) //nolint
		log.Printf("[evonet] → read_file_b64: %s (offset=%d, size=%d)", p.Path, p.Offset, p.Size)
	case "write_file_b64":
		var p writeFileB64Params
		json.Unmarshal(req.Params, &p) //nolint
		log.Printf("[evonet] → write_file_b64: %s (offset=%d, is_last=%v, %d b64 bytes)", p.Path, p.Offset, p.IsLast, len(p.Data))
	default:
		log.Printf("[evonet] → %s", req.Method)
	}
}

func (e *Executor) logResponse(method string, resp Response, dur time.Duration) {
	if !resp.OK {
		log.Printf("[evonet] ← %s ERROR: %s (%.2fs)", method, resp.Error, dur.Seconds())
		return
	}
	switch method {
	case "exec_bash", "exec_python":
		if r, ok := resp.Result.(execResult); ok {
			out := r.Stdout
			if out == "" {
				out = r.Stderr
			}
			log.Printf("[evonet] ← %s OK (exit %d, %.2fs)%s",
				method, r.ExitCode, dur.Seconds(), inlineIfNotEmpty(truncateN(out, 120)))
			return
		}
	case "read_file":
		if r, ok := resp.Result.(map[string]any); ok {
			log.Printf("[evonet] ← read_file OK (%v bytes, %.2fs)", r["size"], dur.Seconds())
			return
		}
	}
	log.Printf("[evonet] ← %s OK (%.2fs)", method, dur.Seconds())
}

// scriptSnippet returns the first 3 lines of a script, truncated to 200 chars total.
func scriptSnippet(s string) string {
	s = strings.TrimSpace(s)
	lines := strings.SplitN(s, "\n", 4)
	if len(lines) > 3 {
		lines = append(lines[:3], "...")
	}
	out := strings.Join(lines, "\n")
	return truncateN(out, 200)
}

func truncateN(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}

func inlineIfNotEmpty(s string) string {
	s = strings.TrimSpace(s)
	if s == "" {
		return ""
	}
	return "\n          " + strings.ReplaceAll(s, "\n", "\n          ")
}

func errResp(id, msg string) Response {
	return Response{ID: id, OK: false, Error: msg}
}

func okResp(id string, result any) Response {
	return Response{ID: id, OK: true, Result: result}
}
