# Hidden pass_to_pass regression guard for oss-tornado-urlencoded-field-limit.
#
# Adding the max_num_fields limit must not change ordinary parsing: without the
# limit, parse_qs_bytes still parses correctly and imposes no field cap. Uses only
# the pre-existing signature (no max_num_fields), so it runs at the base commit and
# after the fix. Run with pytest.

from tornado.escape import parse_qs_bytes


def test_ordinary_parse_unaffected():
    result = parse_qs_bytes("a=1&b=2&a=3")
    assert result["a"] == [b"1", b"3"]
    assert result["b"] == [b"2"]


def test_no_limit_allows_many_fields():
    result = parse_qs_bytes("&".join("k%d=1" % i for i in range(50)))
    assert len(result) == 50
