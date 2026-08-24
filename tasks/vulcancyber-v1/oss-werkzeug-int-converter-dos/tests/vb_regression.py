# Hidden pass_to_pass regression guard for oss-werkzeug-int-converter-dos.
#
# Rejecting over-limit integers must not change ordinary integer routing: a normal
# integer still matches and converts, and an integer with a digit count within the
# limit still matches. Both hold at the base commit and after the fix. Run with pytest.

from werkzeug.routing import Map, Rule


def adapter():
    return Map([Rule("/n/<int:num>", endpoint="n")]).bind("example.com")


def test_normal_integer_matches():
    assert adapter().match("/n/123") == ("n", {"num": 123})


def test_integer_within_digit_limit_matches():
    # 4300 digits is at Python's default int-string limit, so int() still accepts it.
    endpoint, args = adapter().match("/n/" + "1" + "0" * 4299)
    assert endpoint == "n"
    assert args["num"] == 10 ** 4299
