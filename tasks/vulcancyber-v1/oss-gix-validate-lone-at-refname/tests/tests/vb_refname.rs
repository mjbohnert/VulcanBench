// Hidden fail_to_pass tests for oss-gix-validate-lone-at-refname (GitoxideLabs/gitoxide PR #2886).
//
// A lone "@" is Git's shorthand for HEAD, and Git refuses to create a reference
// literally named "@" (it sanitizes it away). This validator accepted "@" as a
// valid partial reference name, and its sanitizing variant left "@" unchanged --
// so a caller could create/ös reference a ref that collides with the HEAD
// shorthand (reference confusion / spoofing). The fix rejects a name that reduces
// to exactly "@": name_partial returns a Reserved error, and the sanitizing
// variant replaces it with "-", matching Git.
//
// At the base commit these pass "@" through, so the assertions below fail. Run with
// `cargo test --offline`.

use bstr::ByteSlice;
use gix_validate::reference;

#[test]
fn lone_at_is_rejected() {
    assert!(reference::name_partial(b"@".as_bstr()).is_err());
}

#[test]
fn lone_at_sanitizes_to_dash() {
    assert_eq!(reference::name_partial_or_sanitize(b"@".as_bstr()).to_string(), "-");
}

#[test]
fn at_between_slashes_sanitizes_to_dash() {
    // Reduces to a lone "@" after slash handling, so it must sanitize to "-", not "@".
    assert_eq!(reference::name_partial_or_sanitize(b"//@//".as_bstr()).to_string(), "-");
}
