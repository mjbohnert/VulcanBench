// Hidden fail_to_pass tests for oss-gosec-g404-weak-random-coverage (securego/gosec PR #1694).
//
// gosec's G404 rule flags use of the insecure math/rand package for
// security-sensitive randomness. At the base commit its function list is
// incomplete: rand.Perm, rand.Shuffle, and rand.ExpFloat64 are NOT flagged, so a
// program that seeds security decisions from these weak sources passes the scanner
// (a false negative — a real detection gap in a security tool). The fix adds the
// missing functions so they are reported.
//
// These tests drive the public gosec analyzer over an in-memory sample and assert
// G404 fires. At the base commit each newly-covered function yields zero issues,
// so the test fails. External package: uses only gosec's public API + testutils.

package vbcheck

import (
	"testing"

	"github.com/securego/gosec/v2"
	"github.com/securego/gosec/v2/rules"
	"github.com/securego/gosec/v2/testutils"
)

// g404Issues runs the G404 rule alone over one Go source sample and returns the
// number of issues reported.
func g404Issues(t *testing.T, code string) int {
	t.Helper()
	logger, _ := testutils.NewLogger()
	analyzer := gosec.NewAnalyzer(nil, false, false, false, 1, logger)
	analyzer.LoadRules(rules.Generate(false, rules.NewRuleFilter(false, "G404")).RulesInfo())
	pkg := testutils.NewTestPackage()
	defer pkg.Close()
	pkg.AddFile("sample.go", code)
	if err := pkg.Build(); err != nil {
		t.Fatalf("failed to build sample: %v", err)
	}
	if err := analyzer.Process([]string{}, pkg.Path); err != nil {
		t.Fatalf("analyzer failed: %v", err)
	}
	issues, _, _ := analyzer.Report()
	return len(issues)
}

func TestG404FlagsPerm(t *testing.T) {
	code := "package main\n\nimport \"math/rand\"\n\nfunc main() {\n\t_ = rand.Perm(10)\n}\n"
	if n := g404Issues(t, code); n == 0 {
		t.Fatalf("G404 must flag math/rand.Perm as weak randomness, got %d issues", n)
	}
}

func TestG404FlagsShuffle(t *testing.T) {
	code := "package main\n\nimport \"math/rand\"\n\nfunc main() {\n\trand.Shuffle(3, func(i, j int) {})\n}\n"
	if n := g404Issues(t, code); n == 0 {
		t.Fatalf("G404 must flag math/rand.Shuffle as weak randomness, got %d issues", n)
	}
}

func TestG404FlagsExpFloat64(t *testing.T) {
	code := "package main\n\nimport \"math/rand\"\n\nfunc main() {\n\t_ = rand.ExpFloat64()\n}\n"
	if n := g404Issues(t, code); n == 0 {
		t.Fatalf("G404 must flag math/rand.ExpFloat64 as weak randomness, got %d issues", n)
	}
}
