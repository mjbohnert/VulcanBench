"""Hidden behavioral tests for oss-flask-automatic-options-override (flask #5917).

Flask can auto-handle ``OPTIONS`` for a route. A view may *force* that on by
setting ``provide_automatic_options`` (as a view attribute or an ``add_url_rule``
argument) even though ``OPTIONS`` isn't in its method list — but the force-on path
was ignored, so no automatic ``OPTIONS`` handler was installed. Graded through the
public Flask test client (HTTP status / Allow header).
"""

from __future__ import annotations

from flask import Flask


def _app() -> Flask:
    return Flask(__name__)


def _view() -> str:
    return "ok"


# --- fail_to_pass: forcing automatic OPTIONS on was ignored at the base commit -


def test_force_enable_via_view_attribute() -> None:
    app = _app()
    view = _view
    view.provide_automatic_options = True  # type: ignore[attr-defined]
    app.add_url_rule("/a", "a", view, methods=["GET"])
    resp = app.test_client().options("/a")
    assert resp.status_code == 200


def test_force_enable_via_add_url_rule_argument() -> None:
    app = _app()
    app.add_url_rule("/b", "b", _view, methods=["GET"], provide_automatic_options=True)
    resp = app.test_client().options("/b")
    assert resp.status_code == 200


def test_forced_options_reports_allowed_methods() -> None:
    app = _app()
    app.add_url_rule("/c", "c", _view, methods=["GET"], provide_automatic_options=True)
    resp = app.test_client().options("/c")
    assert resp.status_code == 200
    assert "GET" in resp.headers.get("Allow", "")


# --- pass_to_pass: default and force-off behavior unchanged -------------------


def test_default_route_gets_automatic_options() -> None:
    app = _app()
    app.add_url_rule("/d", "d", _view, methods=["GET"])
    assert app.test_client().options("/d").status_code == 200


def test_force_disable_blocks_automatic_options() -> None:
    app = _app()
    app.add_url_rule("/e", "e", _view, methods=["GET"], provide_automatic_options=False)
    assert app.test_client().options("/e").status_code == 405
