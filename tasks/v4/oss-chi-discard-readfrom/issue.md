# `Discard()` is ignored on the `ReadFrom` fast path

`middleware.NewWrapResponseWriter` returns a "fancy" writer when the wrapped
`http.ResponseWriter` implements `http.Flusher`, `http.Hijacker` **and**
`io.ReaderFrom`. That writer implements `io.ReaderFrom` itself, so `io.Copy`
into it delegates straight to the underlying writer's `ReadFrom` — a fast path
that avoids copying through an intermediate buffer.

`Discard()` marks the writer so that subsequent output is counted but **not**
forwarded to the underlying `ResponseWriter`. The `ReadFrom` implementation only
diverts through the buffered write path when a tee writer is set; when it isn't,
it streams directly to the underlying writer and the discard flag is never
consulted.

The result is that after calling `Discard()`, body bytes still reach the client
whenever the response is written with `io.Copy` (or any other `ReadFrom` user)
rather than `Write`.

## Expected behaviour

`ReadFrom` must honour `Discard()` exactly as `Write` does: the bytes are
counted in `BytesWritten()`, but nothing is forwarded to the underlying
`ResponseWriter`. Behaviour without `Discard()` is unchanged — including the tee
writer, which must still receive a copy, and byte accounting, which must not
double-count.

## Acceptance examples

```go
// rec implements Flusher + Hijacker + io.ReaderFrom, so the fancy writer is used.
rec := &fancyRecorder{ResponseRecorder: httptest.NewRecorder()}
ww := middleware.NewWrapResponseWriter(rec, 1)

ww.Discard()

// NOTE: io.Copy prefers a source's WriteTo over a destination's ReadFrom, so a
// source such as *strings.Reader would bypass the path under test entirely.
src := struct{ io.Reader }{strings.NewReader("hello world")}
n, _ := io.Copy(ww, src)

// Nothing reaches the underlying writer...
// rec.sink.String() == ""
// ...but the bytes are still accounted for.
// n == 11 && ww.BytesWritten() == 11

// Repeated copies after Discard() stay suppressed, and Discard() applies to
// everything written after it, including following a plain Write.

// Unaffected without Discard(): the data is delivered, counted once, and a tee
// writer still receives its copy.
```
