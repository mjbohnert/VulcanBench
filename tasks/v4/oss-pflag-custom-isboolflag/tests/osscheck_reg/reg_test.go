// Regression guard: built-in bool flags and ordinary value flags are
// unaffected. Says nothing about custom IsBoolFlag() reporting, so it compiles
// and passes at the base commit.
package osscheck_reg

import (
	"testing"

	"github.com/spf13/pflag"
)

type plainValue struct{ got string }

func (v *plainValue) String() string     { return v.got }
func (v *plainValue) Set(s string) error { v.got = s; return nil }
func (v *plainValue) Type() string       { return "plainValue" }

func TestBuiltinBoolFlagParsesWithoutArgument(t *testing.T) {
	fs := pflag.NewFlagSet("t", pflag.ContinueOnError)
	got := fs.Bool("verbose", false, "built-in bool")
	if err := fs.Parse([]string{"--verbose"}); err != nil {
		t.Fatalf("Parse(--verbose) returned error: %v", err)
	}
	if !*got {
		t.Fatal("built-in bool flag was not set")
	}
}

func TestBuiltinStringFlagRequiresArgument(t *testing.T) {
	fs := pflag.NewFlagSet("t", pflag.ContinueOnError)
	fs.String("name", "", "built-in string")
	if err := fs.Parse([]string{"--name"}); err == nil {
		t.Fatal("expected an error when --name is given no argument")
	}
}

func TestPlainCustomValueRequiresArgument(t *testing.T) {
	fs := pflag.NewFlagSet("t", pflag.ContinueOnError)
	v := &plainValue{}
	fs.Var(v, "thing", "plain custom value")
	if err := fs.Parse([]string{"--thing", "hello"}); err != nil {
		t.Fatalf("Parse returned error: %v", err)
	}
	if v.got != "hello" {
		t.Fatalf("value = %q, want %q", v.got, "hello")
	}
}

// boolLike here mirrors a custom bool-like Value. Supplying the value inline
// with `=` never depended on the flag being recognised as bool-like, so this
// holds at the base commit too.
type boolLike struct{ set bool }

func (b *boolLike) String() string     { return "false" }
func (b *boolLike) Set(s string) error { b.set = s == "true"; return nil }
func (b *boolLike) Type() string       { return "boolLike" }
func (b *boolLike) IsBoolFlag() bool   { return true }

func TestExplicitInlineValueIsHonored(t *testing.T) {
	fs := pflag.NewFlagSet("t", pflag.ContinueOnError)
	b := &boolLike{}
	fs.Var(b, "verbose", "bool-like flag")
	if err := fs.Parse([]string{"--verbose=false"}); err != nil {
		t.Fatalf("Parse(--verbose=false) returned error: %v", err)
	}
	if b.set {
		t.Fatal("explicit --verbose=false should leave the value false")
	}
}
