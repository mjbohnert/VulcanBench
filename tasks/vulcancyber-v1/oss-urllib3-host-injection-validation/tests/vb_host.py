# Hidden fail_to_pass tests for oss-urllib3-host-injection-validation (urllib3/urllib3 PR #5095).
#
# parse_url() did not validate the host component, so a URL whose authority
# contained a control character (CR/LF/NUL/etc.) -- literally or percent-encoded --
# parsed into a Url with that character in .host. Downstream that enables
# host-header / CRLF injection, request splitting/smuggling, and SSRF-style host
# confusion. The fix rejects any host containing a control character or space, and
# rejects percent-encoded control octets, raising LocationParseError.
#
# At the base commit these return a Url (no error), so pytest.raises fails. Run with pytest.

import pytest
from urllib3.exceptions import LocationParseError
from urllib3.util.url import parse_url


def test_newline_in_host_is_rejected():
    with pytest.raises(LocationParseError):
        parse_url("http://victim.example\nInjected/path")


def test_carriage_return_in_host_is_rejected():
    with pytest.raises(LocationParseError):
        parse_url("http://victim.example\rInjected/path")


def test_percent_encoded_null_in_host_is_rejected():
    with pytest.raises(LocationParseError):
        parse_url("http://%00.example/")
