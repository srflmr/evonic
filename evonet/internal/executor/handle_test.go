package executor

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
	"testing"
)

// newTestExecutor builds an Executor rooted at a temp dir.
func newTestExecutor(t *testing.T) (*Executor, string) {
	t.Helper()
	dir := t.TempDir()
	return New(dir, false), dir
}

func bashReq(id, script string) Request {
	params, _ := json.Marshal(map[string]any{"script": script, "timeout": 30})
	return Request{ID: id, Method: "exec_bash", Params: params}
}

// Re-sending the same request id must execute the command exactly once.
func TestHandle_SameID_ExecutesOnce(t *testing.T) {
	e, dir := newTestExecutor(t)
	marker := filepath.Join(dir, "count.txt")
	req := bashReq("req-1", "echo x >> "+marker)

	r1 := e.Handle(req)
	r2 := e.Handle(req) // replay of the same id

	if !r1.OK || !r2.OK {
		t.Fatalf("expected both OK, got %+v / %+v", r1, r2)
	}
	data, err := os.ReadFile(marker)
	if err != nil {
		t.Fatalf("reading marker: %v", err)
	}
	if got := string(data); got != "x\n" {
		t.Errorf("command executed %d time(s) (file=%q), want exactly once", len(got)/2, got)
	}
}

// Concurrent callers with the same id must collapse to a single execution.
func TestHandle_ConcurrentSameID_ExecutesOnce(t *testing.T) {
	e, dir := newTestExecutor(t)
	marker := filepath.Join(dir, "count.txt")
	req := bashReq("req-concurrent", "echo y >> "+marker)

	const n = 8
	var wg sync.WaitGroup
	wg.Add(n)
	for i := 0; i < n; i++ {
		go func() {
			defer wg.Done()
			e.Handle(req)
		}()
	}
	wg.Wait()

	data, err := os.ReadFile(marker)
	if err != nil {
		t.Fatalf("reading marker: %v", err)
	}
	if got := string(data); got != "y\n" {
		t.Errorf("command executed %d time(s) (file=%q), want exactly once", len(got)/2, got)
	}
}

// Distinct ids must each execute independently.
func TestHandle_DifferentIDs_ExecuteSeparately(t *testing.T) {
	e, dir := newTestExecutor(t)
	marker := filepath.Join(dir, "count.txt")
	e.Handle(bashReq("a", "echo z >> "+marker))
	e.Handle(bashReq("b", "echo z >> "+marker))

	data, _ := os.ReadFile(marker)
	if got := string(data); got != "z\nz\n" {
		t.Errorf("got %q, want two executions", got)
	}
}

// An empty id bypasses the cache and always executes.
func TestHandle_EmptyID_NotCached(t *testing.T) {
	e, dir := newTestExecutor(t)
	marker := filepath.Join(dir, "count.txt")
	e.Handle(bashReq("", "echo w >> "+marker))
	e.Handle(bashReq("", "echo w >> "+marker))

	data, _ := os.ReadFile(marker)
	if got := string(data); got != "w\nw\n" {
		t.Errorf("got %q, want two executions for empty id", got)
	}
}
