// SPDX-License-Identifier: MIT
// Hidden fail_to_pass tests for oss-echo-encoded-path-separator (labstack/echo PR #3009,
// GHSA-vfp3-v2gw-7wfq). The router matches routes against the raw, still-encoded request
// path, so an encoded path separator (%2F / %5C, and their case/double-encoded variants)
// is not a segment boundary during routing. The static file handler then unescapes the
// wildcard, turning the encoded separator into a real one and resolving a file outside the
// route the router authorized — bypassing route-level middleware (e.g. auth on /admin).
// At the base commit these requests reach the file and leak it; the fix rejects an encoded
// separator with 404 before unescaping. External package: uses only echo's public API.

package vbcheck

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"testing/fstest"

	"github.com/labstack/echo/v5"
	"github.com/stretchr/testify/assert"
)

// A static tree mounted at "/" that also has a protected /admin group. The router
// matches /admin/* (auth) on the raw path; an encoded separator must not let a
// static request sneak a file out of admin/ past that group.
func newProtectedApp() *echo.Echo {
	fsys := fstest.MapFS{
		"admin/secret.txt": {Data: []byte("TOP-SECRET")},
		"index.html":       {Data: []byte("public")},
	}
	e := echo.New()
	g := e.Group("/admin", func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c *echo.Context) error { return c.String(http.StatusForbidden, "denied") }
	})
	g.GET("/*", func(c *echo.Context) error { return c.String(http.StatusOK, "reached-protected-handler") })
	e.StaticFS("/", fsys)
	return e
}

func serve(e *echo.Echo, target string) (int, string) {
	req := httptest.NewRequest(http.MethodGet, target, nil)
	rec := httptest.NewRecorder()
	e.ServeHTTP(rec, req)
	return rec.Code, rec.Body.String()
}

func TestVbEncodedSlashRejected(t *testing.T) {
	code, body := serve(newProtectedApp(), "/admin%2Fsecret.txt")
	assert.Equal(t, http.StatusNotFound, code, "encoded %%2F separator must be rejected")
	assert.NotContains(t, body, "TOP-SECRET", "must not leak the protected file")
}

func TestVbLowercaseEncodedSlashRejected(t *testing.T) {
	code, body := serve(newProtectedApp(), "/admin%2fsecret.txt")
	assert.Equal(t, http.StatusNotFound, code, "lower-case encoded %%2f separator must be rejected")
	assert.NotContains(t, body, "TOP-SECRET", "must not leak the protected file")
}

func TestVbDoubleEncodedSlashRejected(t *testing.T) {
	code, body := serve(newProtectedApp(), "/admin%252Fsecret.txt")
	assert.Equal(t, http.StatusNotFound, code, "double-encoded %%252F must not resolve a separator")
	assert.NotContains(t, body, "TOP-SECRET", "must not leak the protected file")
}
