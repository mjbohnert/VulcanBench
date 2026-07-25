// Hidden grader tests for custom Value implementations that report
// IsBoolFlag() == true.
//
// A Value whose IsBoolFlag() returns true is a boolean-like flag and must be
// usable without an argument, regardless of what its Type() reports. A Value
// whose IsBoolFlag() returns false must keep requiring an argument.
//
// All assertions go through the public pflag API.
package osscheck

import (
	"fmt"
	"testing"

	"github.com/spf13/pflag"
)

// boolLike reports IsBoolFlag() == true but deliberately has a Type() other
// than "bool".
type boolLike struct{ set bool }

func (b *boolLike) String() string     { return fmt.Sprintf("%v", b.set) }
func (b *boolLike) Set(s string) error { b.set = s == "true"; return nil }
func (b *boolLike) Type() string       { return "boolLike" }
func (b *boolLike) IsBoolFlag() bool   { return true }

// valueLike implements the same IsBoolFlag() method but reports false, so it
// is an ordinary value flag that requires an argument.
type valueLike struct{ got string }

func (v *valueLike) String() string     { return v.got }
func (v *valueLike) Set(s string) error { v.got = s; return nil }
func (v *valueLike) Type() string       { return "valueLike" }
func (v *valueLike) IsBoolFlag() bool   { return false }

func TestBoolLikeValueGetsNoOptDefVal(t *testing.T) {
	fs := pflag.NewFlagSet("t", pflag.ContinueOnError)
	fs.Var(&boolLike{}, "verbose", "bool-like flag")
	if got := fs.Lookup("verbose").NoOptDefVal; got != "true" {
		t.Fatalf("NoOptDefVal = %q, want %q", got, "true")
	}
}

func TestBoolLikeValueParsesWithoutArgument(t *testing.T) {
	fs := pflag.NewFlagSet("t", pflag.ContinueOnError)
	b := &boolLike{}
	fs.Var(b, "verbose", "bool-like flag")
	if err := fs.Parse([]string{"--verbose"}); err != nil {
		t.Fatalf("Parse(--verbose) returned error: %v", err)
	}
	if !b.set {
		t.Fatal("flag value was not set to true")
	}
}

func TestBoolLikeValueFollowedByPositionalArg(t *testing.T) {
	fs := pflag.NewFlagSet("t", pflag.ContinueOnError)
	b := &boolLike{}
	fs.Var(b, "verbose", "bool-like flag")
	if err := fs.Parse([]string{"--verbose", "positional"}); err != nil {
		t.Fatalf("Parse returned error: %v", err)
	}
	if !b.set {
		t.Fatal("flag value was not set to true")
	}
	if args := fs.Args(); len(args) != 1 || args[0] != "positional" {
		t.Fatalf("Args() = %v, want [positional]", args)
	}
}

