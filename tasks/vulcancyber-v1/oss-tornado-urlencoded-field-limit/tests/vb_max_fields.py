# Hidden fail_to_pass tests for oss-tornado-urlencoded-field-limit (tornadoweb/tornado PR #3704).
#
# parse_qs_bytes() parses untrusted urlencoded data with no cap on the number of
# fields. A request with a very large number of parameters forces the server to
# build an equally large structure (and downstream per-argument work) — an
# algorithmic denial-of-service reachable from a single request body. The fix adds
# a keyword-only `max_num_fields` limit that raises ValueError when exceeded
# (forwarded to the stdlib parser).
#
# At the base commit parse_qs_bytes has no max_num_fields parameter, so each call
# below raises TypeError (unexpected keyword) and the test fails. After the fix the
# limit is enforced. Run with pytest.

import pytest

from tornado.escape import parse_qs_bytes


def _qs(n):
    return "&".join("a%d=1" % i for i in range(n))


def test_over_limit_raises_value_error():
    with pytest.raises(ValueError):
        parse_qs_bytes(_qs(20), max_num_fields=5)


def test_at_limit_parses_successfully():
    result = parse_qs_bytes(_qs(5), max_num_fields=5)
    assert len(result) == 5


def test_repeated_key_counts_toward_limit():
    # Six fields that share one key still count as six fields against the limit.
    with pytest.raises(ValueError):
        parse_qs_bytes("a=1&a=2&a=3&a=4&a=5&a=6", max_num_fields=3)
