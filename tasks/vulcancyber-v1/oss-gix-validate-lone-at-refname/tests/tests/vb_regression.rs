// Hidden pass_to_pass regression guard for oss-gix-validate-lone-at-refname.
//
// Rejecting a lone "@" must not reject an "@" that appears inside a normal
// reference name, nor any ordinary name. Both hold at the base commit and after
// the fix. Run with `cargo test --offline`.

use bstr::ByteSlice;
use gix_validate::reference;

#[test]
fn at_inside_a_component_is_valid() {
    assert!(reference::name_partial(b"refs/heads/@".as_bstr()).is_ok());
}

#[test]
fn ordinary_name_is_valid() {
    assert!(reference::name_partial(b"refs/heads/main".as_bstr()).is_ok());
}
