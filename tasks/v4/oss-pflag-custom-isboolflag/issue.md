# Custom `Value` implementations reporting `IsBoolFlag() == true` still require an argument

A flag value may opt into boolean-like behaviour by implementing:

```go
IsBoolFlag() bool
```

alongside the `Value` interface. A boolean-like flag can be given on the command
line without an argument (`--verbose`), because its `NoOptDefVal` is `"true"`.

Today that only works for values whose `Type()` is literally `"bool"`. A custom
`Value` that returns `true` from `IsBoolFlag()` but reports some other `Type()`
never has `NoOptDefVal` assigned, so parsing `--verbose` fails with
`flag needs an argument: --verbose`.

Conversely, the code decides "is this a bool flag?" by type-asserting to the
bool-flag interface without ever calling `IsBoolFlag()`, so a value that
implements the method and returns `false` is still treated as boolean-like in
some paths.

## Expected behaviour

`IsBoolFlag()` must be the authority:

- A `Value` implementing `IsBoolFlag()` that returns **true** is boolean-like.
  It gets `NoOptDefVal = "true"` when no explicit `NoOptDefVal` was set, and may
  be given without an argument — whatever its `Type()` reports.
- A `Value` implementing `IsBoolFlag()` that returns **false** is an ordinary
  value flag and keeps requiring an argument.

Built-in flags, and custom values that don't implement `IsBoolFlag()` at all,
are unaffected.

## Acceptance examples

```go
type boolLike struct{ set bool }

func (b *boolLike) String() string     { return fmt.Sprintf("%v", b.set) }
func (b *boolLike) Set(s string) error { b.set = s == "true"; return nil }
func (b *boolLike) Type() string       { return "boolLike" } // NOT "bool"
func (b *boolLike) IsBoolFlag() bool   { return true }

fs := pflag.NewFlagSet("t", pflag.ContinueOnError)
b := &boolLike{}
fs.Var(b, "verbose", "bool-like flag")

// NoOptDefVal is assigned automatically.
// fs.Lookup("verbose").NoOptDefVal == "true"

// The flag parses with no argument, and b.set becomes true.
_ = fs.Parse([]string{"--verbose"})

// A following operand stays a positional argument rather than being consumed.
// fs.Parse([]string{"--verbose", "positional"}) leaves fs.Args() == ["positional"]

// Unaffected: an explicit inline value is still honoured.
// fs.Parse([]string{"--verbose=false"}) leaves b.set == false

// Unaffected: built-in flags, and custom values without IsBoolFlag().
// fs.Bool("v", false, "")     parses as --v
// fs.String("name", "", "")   still requires an argument
```
