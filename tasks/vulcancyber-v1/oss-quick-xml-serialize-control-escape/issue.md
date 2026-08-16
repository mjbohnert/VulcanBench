# Control characters are not escaped when writing XML, corrupting values

When serializing XML, certain control characters are written literally even
though a conformant XML parser will silently rewrite them when the document is
read back:

- A carriage return (`\r`) in **text content** is rewritten to a line feed
  (`\n`) by XML end-of-line normalization.
- A line feed (`\n`) or tab (`\t`) inside an **attribute value** is rewritten to
  a space by attribute-value normalization.

So a value containing these characters does not survive a write/read round-trip —
the data is silently changed. In attribute context this also lets a crafted value
alter the parsed content (smuggling or truncating data) once re-parsed.

## Expected behaviour

When writing XML, escape these characters as numeric character references so they
survive normalization:

- in text content: `\r` → `&#13;`
- in attribute values: `\r` → `&#13;`, `\n` → `&#10;`, `\t` → `&#9;`

The ordinary XML metacharacters (`<`, `>`, `&`, `"`, `'`) must still be escaped
exactly as before, and values without control characters must be written
unchanged.

The relevant code is the escaping in `src/escape.rs` and its use when writing
attribute values in `src/events/attributes.rs`.
