// Hidden fail_to_pass tests for oss-quick-xml-serialize-control-escape (tafia/quick-xml PR #1001).
//
// XML end-of-line and attribute-value normalization silently rewrites certain
// control characters: a `\r` in text is normalized to `\n`, and a `\n` or `\t`
// inside an attribute value is normalized to a space. If those characters are
// written literally, the serialized document does not round-trip — a value with
// embedded control characters is corrupted (and, in attribute context, can be
// used to smuggle or truncate data). The fix escapes them as numeric character
// references (`&#13;`, `&#10;`, `&#9;`) so they survive normalization.
//
// These tests use only pre-existing public API (quick_xml::escape::escape and the
// Writer/attribute path), so they compile at the base commit; there they assert on
// output that base does not produce, so they fail. Run with `cargo test --offline`.

use quick_xml::escape::escape;
use quick_xml::events::{BytesStart, Event};
use quick_xml::Writer;

fn write_element_with_attr(key: &str, value: &str) -> String {
    let mut writer = Writer::new(Vec::new());
    let mut elem = BytesStart::new("e");
    elem.push_attribute((key, value));
    writer.write_event(Event::Start(elem)).unwrap();
    String::from_utf8(writer.into_inner()).unwrap()
}

#[test]
fn carriage_return_in_text_is_escaped() {
    let escaped = escape("line1\rline2");
    assert!(
        escaped.contains("&#13;"),
        "a carriage return must be escaped so XML EOL normalization cannot turn it into \\n; got {escaped:?}"
    );
    assert!(!escaped.contains('\r'), "no literal CR should remain; got {escaped:?}");
}

#[test]
fn newline_in_attribute_value_is_escaped() {
    let out = write_element_with_attr("k", "a\nb");
    assert!(
        out.contains("&#10;"),
        "a newline in an attribute value must be escaped so it is not normalized to a space; got {out:?}"
    );
    assert!(!out.contains("a\nb"), "no literal newline should remain in the attribute; got {out:?}");
}

#[test]
fn tab_in_attribute_value_is_escaped() {
    let out = write_element_with_attr("k", "a\tb");
    assert!(
        out.contains("&#9;"),
        "a tab in an attribute value must be escaped so it is not normalized to a space; got {out:?}"
    );
    assert!(!out.contains("a\tb"), "no literal tab should remain in the attribute; got {out:?}");
}
