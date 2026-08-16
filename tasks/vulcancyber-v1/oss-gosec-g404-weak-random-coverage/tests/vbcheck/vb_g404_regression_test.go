// Hidden pass_to_pass regression guard for oss-gosec-g404-weak-random-coverage.
//
// Extending G404's coverage must not change its existing behaviour: an
// already-covered weak function is still flagged, and a secure source
// (crypto/rand) still produces no G404 finding (no false positive). Both hold at
// the base commit and after the fix. Reuses g404Issues from the fail_to_pass file.

package vbcheck

import "testing"

func TestG404StillFlagsIntn(t *testing.T) {
	code := "package main\n\nimport \"math/rand\"\n\nfunc main() {\n\t_ = rand.Intn(10)\n}\n"
	if n := g404Issues(t, code); n == 0 {
		t.Fatalf("G404 must still flag math/rand.Intn, got %d issues", n)
	}
}

func TestG404IgnoresCryptoRand(t *testing.T) {
	code := "package main\n\nimport (\n\tcrand \"crypto/rand\"\n)\n\nfunc main() {\n\tb := make([]byte, 16)\n\t_, _ = crand.Read(b)\n}\n"
	if n := g404Issues(t, code); n != 0 {
		t.Fatalf("G404 must not flag crypto/rand (secure), got %d issues", n)
	}
}
