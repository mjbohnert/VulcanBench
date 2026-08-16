# Hidden fail_to_pass tests for oss-werkzeug-etag-strict-parse (pallets/werkzeug PR #3234).
#
# ETag headers (If-Match / If-None-Match) are parsed into an ETags collection used
# for conditional-request decisions. The parser accepted invalid *unquoted* values
# in addition to well-formed quoted ETags, so a malformed header entry became a
# real ETag that could satisfy a match it should not. The fix parses only
# syntactically valid (quoted) ETags and discards invalid items.
#
# At the base commit an invalid unquoted value is kept and matches, so the
# assertions below fail. Run with pytest.

from werkzeug.http import parse_etags


def test_invalid_unquoted_value_is_discarded():
    etags = parse_etags('"a", bad, "b"')
    assert etags.as_set() == {"a", "b"}


def test_invalid_value_does_not_match():
    etags = parse_etags('"a", bad')
    assert "bad" not in etags


def test_all_invalid_header_parses_empty():
    etags = parse_etags("bad1, bad2")
    assert etags.as_set() == set()
