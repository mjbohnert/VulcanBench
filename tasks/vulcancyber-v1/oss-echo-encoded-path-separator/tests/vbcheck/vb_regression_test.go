// SPDX-License-Identifier: MIT
// Hidden pass_to_pass regression guard for oss-echo-encoded-path-separator.
// Rejecting encoded separators must not break ordinary static serving: a normal
// static file is still served, and a plain (unencoded) path into the protected
// group is still handled by the group's middleware. Both hold at the base commit
// and after the fix. External package: uses only echo's public API.

package vbcheck

import (
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestVbLegitStaticStillServed(t *testing.T) {
	code, body := serve(newProtectedApp(), "/index.html")
	assert.Equal(t, http.StatusOK, code, "a legitimate static file must still be served")
	assert.Equal(t, "public", body)
}

// An encoded backslash decodes to a literal filename character (not a separator on
// fs.FS), so it resolves nothing and is already Not Found — guard that this stays
// true and never regresses into serving a file.
func TestVbEncodedBackslashStaysNotFound(t *testing.T) {
	code, body := serve(newProtectedApp(), "/admin%5Csecret.txt")
	assert.Equal(t, http.StatusNotFound, code)
	assert.NotContains(t, body, "TOP-SECRET")
}
