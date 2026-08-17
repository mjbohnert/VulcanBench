# Forcing `provide_automatic_options` on is ignored

Flask can install an automatic `OPTIONS` handler for a route. Normally this happens
by default (controlled by `PROVIDE_AUTOMATIC_OPTIONS`), but a view can also *force*
it on explicitly — either by setting `provide_automatic_options = True` as an
attribute on the view function, or by passing `provide_automatic_options=True` to
`add_url_rule`.

That force-on path doesn't work: when the flag is explicitly `True` but `OPTIONS`
is not among the route's declared methods, no automatic `OPTIONS` handler is
installed, so an `OPTIONS` request returns `405 Method Not Allowed`.

```python
from flask import Flask

app = Flask(__name__)

def view():
    return "ok"

app.add_url_rule("/x", "x", view, methods=["GET"], provide_automatic_options=True)
app.test_client().options("/x").status_code   # 405, expected 200
```

## Expected behavior

- Forcing automatic options on — via the `provide_automatic_options=True` view
  attribute or the `add_url_rule` argument — installs the automatic `OPTIONS`
  handler, so an `OPTIONS` request returns `200` (with `GET` present in the `Allow`
  header).
- Unchanged: a normal route still gets automatic `OPTIONS` by default, and
  `provide_automatic_options=False` still disables it (`OPTIONS` → `405`).

Fix `add_url_rule` so an explicitly enabled `provide_automatic_options` actually
installs the automatic `OPTIONS` handling.
