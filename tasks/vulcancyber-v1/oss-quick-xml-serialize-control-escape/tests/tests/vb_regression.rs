// Hidden pass_to_pass regression guard for oss-quick-xml-serialize-control-escape.
//
// Escaping additional control characters must not change how the ordinary XML
// metacharacters are escaped, nor how a plain attribute is written. Both hold at
// the base commit and after the fix. Run with `cargo test --offline`.

use quick_xml::escape::escape;
use quick_xml::events::{BytesStart, Event};
use quick_xml::Writer;

#[test]
fn ordinary_metacharacters_still_escaped() {
    let escaped = escape("a<b>&c\"d'e");
    assert!(escaped.contains("&lt;"));
    assert!(escaped.contains("&gt;"));
    assert!(escaped.contains("&amp;"));
    // The five XML predefined entities must be unchanged; no literal <, >, & remain.
    assert!(!escaped.contains('<'));
    assert!(!escaped.contains('>'));
    assert!(!escaped.contains('&') || escaped.contains("&amp;"));
}

#[test]
fn plain_attribute_value_is_written_verbatim() {
    let mut writer = Writer::new(Vec::new());
    let mut elem = BytesStart::new("e");
    elem.push_attribute(("k", "plain-value"));
    writer.write_event(Event::Start(elem)).unwrap();
    let out = String::from_utf8(writer.into_inner()).unwrap();
    assert!(out.contains("k=\"plain-value\""), "got {out:?}");
}
