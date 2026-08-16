# Hidden pass_to_pass regression guard for oss-werkzeug-host-port-validation.
#
# Validating the port must not change the decision for well-formed hosts: a
# trusted host with a valid port, and a trusted host with no port, are still
# trusted; an untrusted host is still rejected. All hold at the base commit and
# after the fix. Run with pytest.

from werkzeug.sansio.utils import host_is_trusted

TRUSTED = ["example.com"]


def test_valid_port_is_trusted():
    assert host_is_trusted("example.com:8080", TRUSTED) is True


def test_no_port_is_trusted():
    assert host_is_trusted("example.com", TRUSTED) is True


def test_untrusted_host_is_rejected():
    assert host_is_trusted("evil.example.org:8080", TRUSTED) is False
