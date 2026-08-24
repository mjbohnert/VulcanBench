# Hidden fail_to_pass tests for oss-werkzeug-int-converter-dos (pallets/werkzeug PR #3238).
#
# The URL routing `<int:...>` converter calls int() on the matched path segment.
# Python caps int()-from-string at ~4300 digits (CVE-2020-10735 mitigation) and
# raises ValueError above that. The converter did not catch it, so a request URL
# with a very long run of digits made routing raise an unhandled ValueError
# (a 500 / crash) instead of simply not matching the route -- a denial-of-service
# from a single request. The fix catches the ValueError and treats the segment as
# a non-match, yielding a normal 404.
#
# At the base commit these raise ValueError (not NotFound), so the assertions fail.
# Run with pytest.

import pytest
from werkzeug.exceptions import NotFound
from werkzeug.routing import Map, Rule


def adapter():
    return Map([Rule("/n/<int:num>", endpoint="n")]).bind("example.com")


def test_5000_digit_int_url_is_not_found():
    with pytest.raises(NotFound):
        adapter().match("/n/" + "9" * 5000)


def test_10000_digit_int_url_is_not_found():
    with pytest.raises(NotFound):
        adapter().match("/n/" + "9" * 10000)


def test_just_over_limit_int_url_is_not_found():
    with pytest.raises(NotFound):
        adapter().match("/n/" + "9" * 4301)
