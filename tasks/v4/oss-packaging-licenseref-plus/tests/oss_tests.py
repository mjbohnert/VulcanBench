"""Hidden grader tests: a `+` suffix on a LicenseRef must be reported as an
invalid license expression, not surface as a bare KeyError.

Assertions check only the exception type raised by the public
canonicalize_license_expression API -- never the message text.
"""

import pytest

from packaging.licenses import InvalidLicenseExpression, canonicalize_license_expression


def test_licenseref_with_plus_raises_invalid_expression():
    with pytest.raises(InvalidLicenseExpression):
        canonicalize_license_expression('LicenseRef-Foo+')


def test_licenseref_with_plus_inside_compound_expression():
    with pytest.raises(InvalidLicenseExpression):
        canonicalize_license_expression('MIT OR LicenseRef-Foo+')


def test_licenseref_with_plus_does_not_raise_keyerror():
    # The pre-fix failure mode was an unhandled KeyError leaking out of the
    # normalization table lookup.
    with pytest.raises(Exception) as excinfo:
        canonicalize_license_expression('LicenseRef-Foo+')
    assert not isinstance(excinfo.value, KeyError)


def test_multiple_licenserefs_with_plus():
    for expr in ('LicenseRef-A+', 'LicenseRef-Some-Thing+', 'MIT AND LicenseRef-B+'):
        with pytest.raises(InvalidLicenseExpression):
            canonicalize_license_expression(expr)
