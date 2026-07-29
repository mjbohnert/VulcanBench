"""Regression guard: valid expressions and pre-existing rejections.

Says nothing about a `+` on a LicenseRef, so it passes at the base commit.
"""

import pytest

from packaging.licenses import InvalidLicenseExpression, canonicalize_license_expression


def test_plain_licenseref_is_accepted():
    assert canonicalize_license_expression('LicenseRef-Foo') == 'LicenseRef-Foo'


def test_license_id_with_plus_is_accepted():
    assert canonicalize_license_expression('MIT+') == 'MIT+'


def test_license_ids_are_normalized():
    assert canonicalize_license_expression('mit') == 'MIT'
    assert canonicalize_license_expression('MIT OR Apache-2.0') == 'MIT OR Apache-2.0'


def test_unknown_license_id_still_rejected():
    with pytest.raises(InvalidLicenseExpression):
        canonicalize_license_expression('Bogus-1.0')
