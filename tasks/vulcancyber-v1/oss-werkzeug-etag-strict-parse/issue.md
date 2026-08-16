# ETag parsing accepts invalid, unquoted values

ETag headers (`If-Match`, `If-None-Match`) are parsed into an `ETags` collection
that drives conditional-request decisions. The parser accepts **invalid,
unquoted** values in addition to well-formed quoted ETags. A malformed header
entry therefore becomes a real ETag in the collection and can satisfy a match it
should never satisfy — weakening the conditional-request check.

## Expected behaviour

Parse only syntactically valid ETags (quoted values, optionally weak `W/"..."`),
and **discard** invalid items:

- an invalid unquoted value is not added to the parsed set;
- an invalid value does not match (is not "in" the collection);
- a header made up entirely of invalid values parses to an empty collection.

Well-formed quoted ETags must still parse and still match exactly as before.

The parsing lives in `src/werkzeug/http.py` / `src/werkzeug/sansio/http.py`, and
the membership check in `src/werkzeug/datastructures/etag.py`.
