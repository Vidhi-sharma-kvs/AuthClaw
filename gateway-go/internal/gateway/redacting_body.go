package gateway

import (
	"io"
	"log"
)

type redactingReadCloser struct {
	source    io.ReadCloser
	redactor *StreamingRedactor
	pending   []byte
	done      bool
	closed    bool
	path      string
}

func newRedactingReadCloser(source io.ReadCloser, path string) io.ReadCloser {
	log.Printf("stream_redaction_start path=%s", path)
	return &redactingReadCloser{
		source:    source,
		redactor: NewStreamingRedactor(),
		path:      path,
	}
}

func (r *redactingReadCloser) Read(p []byte) (int, error) {
	if len(r.pending) > 0 {
		return r.drainPending(p), nil
	}
	if r.done {
		return 0, io.EOF
	}

	for {
		buffer := make([]byte, 4096)
		n, readErr := r.source.Read(buffer)
		if n > 0 {
			out, err := r.redactor.Process(buffer[:n], false)
			if err != nil {
				r.failClosed(err)
				return r.drainPending(p), nil
			}
			if len(out) > 0 {
				r.pending = out
				return r.drainPending(p), nil
			}
		}

		if readErr == io.EOF {
			out, err := r.redactor.Process(nil, true)
			if err != nil {
				r.failClosed(err)
				return r.drainPending(p), nil
			}
			r.done = true
			r.logEnd()
			if len(out) > 0 {
				r.pending = out
				return r.drainPending(p), nil
			}
			return 0, io.EOF
		}

		if readErr != nil {
			r.failClosed(readErr)
			return r.drainPending(p), nil
		}
	}
}

func (r *redactingReadCloser) Close() error {
	if !r.done {
		r.done = true
		r.logEnd()
	}
	if r.closed {
		return nil
	}
	r.closed = true
	return r.source.Close()
}

func (r *redactingReadCloser) drainPending(p []byte) int {
	n := copy(p, r.pending)
	r.pending = r.pending[n:]
	return n
}

func (r *redactingReadCloser) failClosed(err error) {
	log.Printf("stream_redaction_failure path=%s action=safe_placeholder error=%v", r.path, err)
	r.done = true
	r.pending = []byte(streamSafePlaceholder)
	_ = r.source.Close()
	r.logEnd()
}

func (r *redactingReadCloser) logEnd() {
	stats := r.redactor.Stats()
	log.Printf(
		"stream_redaction_end path=%s chunks=%d redactions=%d failures=%d triggers=%s",
		r.path,
		stats.ChunksProcessed,
		stats.RedactionsApplied,
		stats.Failures,
		triggerSummary(stats),
	)
}
