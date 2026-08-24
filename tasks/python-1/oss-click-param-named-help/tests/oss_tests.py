"""Hidden behavioral tests for oss-click-param-named-help (click #3678).

Graded on observable CLI behavior via the public API only — parsed values,
exit codes, help output, and whether a UserWarning fires — never on the
internal storage name the fix happens to choose.
"""

from __future__ import annotations

import warnings

import click
import pytest
from click.testing import CliRunner


def _runner() -> CliRunner:
    return CliRunner()


def _echo_first(**kwargs: object) -> None:
    # Echo the single parsed parameter value the command received.
    click.echo(next(iter(kwargs.values()), None))


# --- fail_to_pass: broken at the base commit, fixed by the patch -------------


def test_argument_named_help_parses_and_help_still_works() -> None:
    """An argument named ``help`` must parse normally, and ``--help`` must still
    print the help page (the two must not collide)."""
    cli = click.Command(
        "cli",
        params=[click.Argument(["help"])],
        callback=_echo_first,
    )
    runner = _runner()

    result = runner.invoke(cli, ["value"])
    assert result.exit_code == 0
    assert result.output == "value\n"

    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Show this message and exit." in result.output


def test_option_aliased_to_help_name_receives_value() -> None:
    """An option whose parameter name is ``help`` must still receive its value
    rather than being clobbered by the automatic help option."""
    cli = click.Command(
        "cli",
        params=[click.Option(["--assist", "help"])],
        callback=_echo_first,
    )
    result = _runner().invoke(cli, ["--assist", "value"])
    assert result.exit_code == 0
    assert result.output == "value\n"


def test_argument_name_collision_warns() -> None:
    """An argument sharing its parameter name with another parameter makes them
    overwrite each other's value during parsing, which must warn."""

    @click.command()
    @click.option("--foo", "target")
    @click.argument("target")
    def cli(target: str) -> None:
        click.echo(target, nl=False)

    with pytest.warns(UserWarning, match="is used by an argument"):
        result = _runner().invoke(cli, ["--foo", "from_option", "from_argument"])
    assert result.exit_code == 0
    assert result.output == "from_argument"


# --- pass_to_pass: green at the base commit and after the patch --------------


def test_plain_command_help_and_option_unaffected() -> None:
    """A command with an ordinary option: normal parsing and ``--help`` both
    keep working. Does not reference the fix; guards against regressions."""

    @click.command()
    @click.option("--name", default="world")
    def cli(name: str) -> None:
        click.echo(f"hi {name}")

    runner = _runner()

    result = runner.invoke(cli, ["--name", "bob"])
    assert result.exit_code == 0
    assert result.output == "hi bob\n"

    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Show this message and exit." in result.output


def test_feature_switch_options_share_name_without_warning() -> None:
    """Options deliberately sharing one parameter name (a feature switch) is a
    supported pattern and must not trigger the duplicate-name warning."""

    @click.command()
    @click.option("--upper", "transformation", flag_value="upper")
    @click.option("--lower", "transformation", flag_value="lower")
    def cli(transformation: str) -> None:
        click.echo(transformation, nl=False)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = _runner().invoke(cli, ["--upper"], catch_exceptions=False)

    assert result.exit_code == 0
    assert result.output == "upper"
    dup = [
        w
        for w in caught
        if issubclass(w.category, UserWarning)
        and ("overwrite" in str(w.message) or "reserved" in str(w.message))
    ]
    assert not dup, f"unexpected duplicate-name warning: {[str(w.message) for w in dup]}"
