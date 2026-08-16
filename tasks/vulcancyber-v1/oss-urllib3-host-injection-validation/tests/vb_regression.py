# Hidden pass_to_pass regression guard for oss-urllib3-host-injection-validation.
#
# Rejecting invalid hosts must not reject well-formed ones: an ordinary domain and
# an IPv4 literal still parse with the expected host. Both hold at the base commit
# and after the fix. Run with pytest.

from urllib3.util.url import parse_url


def test_ordinary_domain_parses():
    assert parse_url("http://example.com/path").host == "example.com"


def test_ipv4_host_parses():
    assert parse_url("http://127.0.0.1/path").host == "127.0.0.1"
