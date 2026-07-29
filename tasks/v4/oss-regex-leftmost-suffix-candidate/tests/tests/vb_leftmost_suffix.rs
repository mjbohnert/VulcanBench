/*!
Hidden grader tests for leftmost-first correctness when a reverse suffix or
reverse inner literal optimization is in play.

When a regex has no usable prefix literal but does have an extractable suffix or
inner literal, the engine scans for that literal to find candidate match
positions. If the first candidate yields a match that starts *later* than a
match confirmed by a subsequent candidate, the earlier-starting match is the
leftmost one and must win.

Every expected span is generated from the gold patch, and all assertions go
through the public `regex::Regex` API.
*/

use regex::Regex;

fn find_span(pattern: &str, haystack: &str) -> (usize, usize) {
    let re = Regex::new(pattern).expect("pattern compiles");
    let m = re.find(haystack).expect("haystack contains a match");
    (m.start(), m.end())
}

#[test]
fn suffix_literal_leftmost_with_dot_prefix() {
    assert_eq!(find_span(r".abb|b", "zabb"), (0, 4));
}

#[test]
fn suffix_literal_leftmost_shorter_alternate() {
    assert_eq!(find_span(r".bb|b", "zabb"), (1, 4));
}

#[test]
fn suffix_literal_leftmost_with_trailing_context() {
    assert_eq!(find_span(r".abb|b", "zzzabbz"), (2, 6));
}

#[test]
fn suffix_literal_leftmost_with_variable_length_prefix() {
    assert_eq!(find_span(r"\s+\w+bb|b", " zabb"), (0, 5));
}

#[test]
fn inner_literal_leftmost_with_bounded_repetition() {
    assert_eq!(find_span(r"(?:[a-wyz]{3}|[a-wyz]).b", "xaaabb"), (1, 6));
}

/// The same leftmost span must be reported through the capture API, not just
/// `find`.
#[test]
fn captures_agree_with_leftmost_span() {
    let re = Regex::new(r".bb|b").unwrap();
    let caps = re.captures("zabb").expect("haystack contains a match");
    let m = caps.get(0).expect("group 0 always present on a match");
    assert_eq!((m.start(), m.end()), (1, 4));
}

/// Iterating matches must also start from the leftmost span.
#[test]
fn find_iter_starts_at_leftmost_span() {
    let re = Regex::new(r".bb|b").unwrap();
    let spans: Vec<(usize, usize)> = re.find_iter("zabb").map(|m| (m.start(), m.end())).collect();
    assert_eq!(spans.first().copied(), Some((1, 4)));
}
