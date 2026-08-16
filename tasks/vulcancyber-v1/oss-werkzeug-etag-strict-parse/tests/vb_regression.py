# Hidden pass_to_pass regression guard for oss-werkzeug-etag-strict-parse.
#
# Rejecting invalid ETags must not change parsing of well-formed ones: valid quoted
# ETags are still parsed and still match, and a valid ETag matches by value. Both
# hold at the base commit and after the fix. Run with pytest.

from werkzeug.http import parse_etags


def test_valid_quoted_etags_parsed():
    etags = parse_etags('"a", "b"')
    assert etags.as_set() == {"a", "b"}


def test_valid_etag_matches():
    etags = parse_etags('"a", "b"')
    assert "a" in etags
    assert "missing" not in etags
