/*!
Regression guard: ordinary matching is unaffected.

These patterns either have a usable prefix literal or place the first literal
candidate at the leftmost match already, so none of them depend on the
candidate-ordering behaviour under test. They compile and pass at the base
commit.
*/

use regex::Regex;

fn find_span(pattern: &str, haystack: &str) -> Option<(usize, usize)> {
    Regex::new(pattern)
        .expect("pattern compiles")
        .find(haystack)
        .map(|m| (m.start(), m.end()))
}

#[test]
fn prefix_literal_alternation_matches_leftmost() {
    assert_eq!(find_span(r"abc|b", "zabcb"), Some((1, 4)));
}

#[test]
fn plain_literal_matches_leftmost() {
    assert_eq!(find_span(r"abb", "zabbabb"), Some((1, 4)));
}

#[test]
fn alternation_prefers_leftmost_then_first() {
    assert_eq!(find_span(r"foo|foobar", "xxfoobar"), Some((2, 5)));
}

#[test]
fn non_matching_haystack_reports_none() {
    assert_eq!(find_span(r".bb|b", "zacc"), None);
}

#[test]
fn anchored_pattern_unaffected() {
    assert_eq!(find_span(r"^a.c", "abcabc"), Some((0, 3)));
}
