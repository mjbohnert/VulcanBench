# Hidden fail_to_pass tests for oss-werkzeug-host-port-validation (pallets/werkzeug PR #3236).
#
# host_is_trusted() decides whether a request's Host header matches the trusted
# host list. It strips the port before comparing but never validates it, so a Host
# header with a malformed or out-of-range port (":0", ":99999", a leading-zero
# port) is still treated as trusted. That weakens Host-header validation, which
# guards against Host-header injection / cache poisoning / bad absolute-URL
# construction. The fix parses and range-checks the port (1..65535, no leading
# zero) and rejects the host when it is invalid.
#
# At the base commit these malformed-port hosts are (wrongly) trusted, so the
# assertions below fail. Run with pytest.

from werkzeug.sansio.utils import host_is_trusted

TRUSTED = ["example.com"]


def test_zero_port_is_not_trusted():
    assert host_is_trusted("example.com:0", TRUSTED) is False


def test_out_of_range_port_is_not_trusted():
    assert host_is_trusted("example.com:99999", TRUSTED) is False


def test_leading_zero_port_is_not_trusted():
    assert host_is_trusted("example.com:08080", TRUSTED) is False
