# A parameter named `help` breaks command parsing

Click automatically adds a `--help` option to every command. Internally that
option stores its value under the parameter name `help`, which collides with any
user-defined parameter that also resolves to the name `help`. When they collide,
one silently overwrites the other and parsing misbehaves.

Reproduce:

```python
import click

cli = click.Command(
    "cli",
    params=[click.Argument(["help"])],
    callback=lambda **kw: click.echo(next(iter(kw.values()), None)),
)
```

Invoking this command with a positional value does not return that value cleanly,
and the collision happens silently.

## Expected behavior

- A user parameter named `help` (an `Argument(["help"])`, or an `Option` whose
  parameter name is `help`) must parse normally and receive its own value.
  Running the command above with `["value"]` should exit 0 and print `value`.
- The automatic `--help` option must keep working: invoking the same command with
  `--help` should still print the standard help page (which contains
  `Show this message and exit.`).
- Two parameters that genuinely resolve to the same name and would therefore
  overwrite each other during parsing — for example an `Argument` and an `Option`
  sharing one name — should emit a `UserWarning` instead of failing silently.
- Options that deliberately share one parameter name to implement a feature switch
  (several `flag_value` options writing to the same name) are a supported pattern
  and must **not** warn.

Fix the command-parameter handling so user parameters no longer collide with the
automatic help option, and so genuinely ambiguous parameter names are reported
rather than silently overwriting each other. Existing behavior for ordinary
commands must be unchanged.
