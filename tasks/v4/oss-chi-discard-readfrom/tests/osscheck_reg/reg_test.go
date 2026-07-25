// Regression guard: ReadFrom without Discard() still delivers data, tee still
// receives a copy, and byte accounting is not double-counted. Says nothing
// about discard semantics, so it compiles and passes at the base commit.
package osscheck_reg

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

func plain(s string) io.Reader { return struct{ io.Reader }{strings.NewReader(s)} }

func newFancy() (*fancyRecorder, middleware.WrapResponseWriter) {
	rec := &fancyRecorder{ResponseRecorder: httptest.NewRecorder()}
	return rec, middleware.NewWrapResponseWriter(rec, 1)
}

func TestReadFromDeliversDataWithoutDiscard(t *testing.T) {
	rec, ww := newFancy()
	if _, err := io.Copy(ww, plain("hello world")); err != nil {
		t.Fatalf("io.Copy returned error: %v", err)
	}
	if got := rec.sink.String(); got != "hello world" {
		t.Fatalf("underlying writer received %q, want %q", got, "hello world")
	}
}

func TestReadFromCountsBytesOnce(t *testing.T) {
	_, ww := newFancy()
	if _, err := io.Copy(ww, plain("hello world")); err != nil {
		t.Fatalf("io.Copy returned error: %v", err)
	}
	if got := ww.BytesWritten(); got != 11 {
		t.Fatalf("BytesWritten() = %d, want 11", got)
	}
}

func TestTeeReceivesCopyOnReadFrom(t *testing.T) {
	rec, ww := newFancy()
	var tee bytes.Buffer
	ww.Tee(&tee)
	if _, err := io.Copy(ww, plain("hello world")); err != nil {
		t.Fatalf("io.Copy returned error: %v", err)
	}
	if got := tee.String(); got != "hello world" {
		t.Fatalf("tee received %q, want %q", got, "hello world")
	}
	// With a tee set, ReadFrom routes through basicWriter.Write, so the data
	// reaches the recorder body rather than its ReadFrom sink.
	if got := rec.ResponseRecorder.Body.String(); got != "hello world" {
		t.Fatalf("recorder body = %q, want %q", got, "hello world")
	}
}

func TestPlainWriteIsUnaffected(t *testing.T) {
	rec, ww := newFancy()
	if _, err := ww.Write([]byte("direct")); err != nil {
		t.Fatalf("Write returned error: %v", err)
	}
	if got := rec.ResponseRecorder.Body.String(); got != "direct" {
		t.Fatalf("recorder body = %q, want %q", got, "direct")
	}
}

func TestDiscardStillReportsBytesWritten(t *testing.T) {
	_, ww := newFancy()
	ww.Discard()
	n, err := io.Copy(ww, plain("hello world"))
	if err != nil {
		t.Fatalf("io.Copy returned error: %v", err)
	}
	if n != 11 {
		t.Fatalf("io.Copy reported n = %d, want 11", n)
	}
	if got := ww.BytesWritten(); got != 11 {
		t.Fatalf("BytesWritten() = %d, want 11", got)
	}
}
