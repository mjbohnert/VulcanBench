// Hidden grader tests for Discard() on the ReadFrom fast path.
//
// When the wrapped ResponseWriter implements Flusher + Hijacker + io.ReaderFrom,
// NewWrapResponseWriter returns the "fancy" writer whose ReadFrom delegates
// straight to the underlying writer. That fast path must still honor Discard().
//
// The readers below deliberately hide io.WriterTo, because io.Copy prefers a
// source's WriteTo over a destination's ReadFrom and would otherwise never
// exercise the path under test.
package osscheck

import (
	"bufio"
	"bytes"
	"errors"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5/middleware"
)

type fancyRecorder struct {
	*httptest.ResponseRecorder
	sink bytes.Buffer
}

func (r *fancyRecorder) ReadFrom(src io.Reader) (int64, error) { return io.Copy(&r.sink, src) }
func (r *fancyRecorder) Hijack() (net.Conn, *bufio.ReadWriter, error) {
	return nil, nil, errors.New("not supported")
}

var _ http.Flusher = &fancyRecorder{}
var _ http.Hijacker = &fancyRecorder{}
var _ io.ReaderFrom = &fancyRecorder{}

// plain hides io.WriterTo from io.Copy.
func plain(s string) io.Reader { return struct{ io.Reader }{strings.NewReader(s)} }

func newFancy() (*fancyRecorder, middleware.WrapResponseWriter) {
	rec := &fancyRecorder{ResponseRecorder: httptest.NewRecorder()}
	return rec, middleware.NewWrapResponseWriter(rec, 1)
}

func TestDiscardSuppressesReadFrom(t *testing.T) {
	rec, ww := newFancy()
	ww.Discard()
	if _, err := io.Copy(ww, plain("hello world")); err != nil {
		t.Fatalf("io.Copy returned error: %v", err)
	}
	if got := rec.sink.String(); got != "" {
		t.Fatalf("underlying writer received %q, want nothing after Discard()", got)
	}
}


func TestDiscardSuppressesRepeatedReadFrom(t *testing.T) {
	rec, ww := newFancy()
	ww.Discard()
	for _, chunk := range []string{"alpha", "beta", "gamma"} {
		if _, err := io.Copy(ww, plain(chunk)); err != nil {
			t.Fatalf("io.Copy(%q) returned error: %v", chunk, err)
		}
	}
	if got := rec.sink.String(); got != "" {
		t.Fatalf("underlying writer received %q, want nothing after Discard()", got)
	}
}

func TestDiscardAfterWriteSuppressesSubsequentReadFrom(t *testing.T) {
	rec, ww := newFancy()
	if _, err := ww.Write([]byte("kept")); err != nil {
		t.Fatalf("Write returned error: %v", err)
	}
	ww.Discard()
	if _, err := io.Copy(ww, plain("dropped")); err != nil {
		t.Fatalf("io.Copy returned error: %v", err)
	}
	if got := rec.sink.String(); got != "" {
		t.Fatalf("ReadFrom after Discard() leaked %q to the underlying writer", got)
	}
}
