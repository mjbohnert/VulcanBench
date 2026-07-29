# A `+` suffix on a `LicenseRef` leaks a `KeyError`

The SPDX license-expression spec allows a trailing `+` on a **license id**, to
mean "this version or later":

```
MIT
MIT+
```

It does **not** allow that suffix on a `LicenseRef`. `LicenseRef-Foo+` is not a
valid expression.

`canonicalize_license_expression` splits any `+` suffix off a token, validates
the remaining `LicenseRef` text, and then looks the token up in its
normalization table with the suffix re-appended. The suffixed form is never
rejected by the validation step and never exists in the table, so the lookup
raises a bare `KeyError` out of the middle of the function instead of the
library's own error type.

Callers that correctly handle `InvalidLicenseExpression` therefore see an
unrelated exception escape.

## Expected behaviour

A `LicenseRef` carrying any suffix is invalid and must raise
`InvalidLicenseExpression`, whether it appears alone or inside a compound
expression. A `+` on a genuine license id keeps working, and plain
`LicenseRef` tokens are still accepted and normalized as before.

## Acceptance examples

```python
from packaging.licenses import (
    InvalidLicenseExpression,
    canonicalize_license_expression,
)

# Invalid: a suffixed LicenseRef, alone or in a compound expression.
# canonicalize_license_expression('LicenseRef-Foo+')        raises InvalidLicenseExpression
# canonicalize_license_expression('MIT OR LicenseRef-Foo+') raises InvalidLicenseExpression
# canonicalize_license_expression('MIT AND LicenseRef-B+')  raises InvalidLicenseExpression
# In particular, a KeyError must not escape.

# Unaffected:
canonicalize_license_expression('LicenseRef-Foo')    == 'LicenseRef-Foo'
canonicalize_license_expression('MIT+')              == 'MIT+'
canonicalize_license_expression('mit')               == 'MIT'
canonicalize_license_expression('MIT OR Apache-2.0') == 'MIT OR Apache-2.0'
# canonicalize_license_expression('Bogus-1.0') raises InvalidLicenseExpression
```
