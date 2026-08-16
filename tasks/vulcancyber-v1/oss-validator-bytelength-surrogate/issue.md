# `isByteLength` crashes on unpaired UTF-16 surrogates

`isByteLength(str, options)` measures a string's length in UTF-8 bytes. It does so
by calling `encodeURI(str)` and counting the result. But `encodeURI` throws a
`URIError` when the string contains **any unpaired UTF-16 surrogate** (a lone
high or low surrogate). So a single lone surrogate in untrusted input makes
`isByteLength` throw — crashing it and every validator that relies on it — an
uncaught-exception denial-of-service.

## Expected behaviour

`isByteLength` must compute the byte length without throwing on unpaired
surrogates. Count each character's UTF-8 size directly:

- a character in the Basic Multilingual Plane uses 1–3 bytes as usual;
- a valid surrogate **pair** (an astral character) is 4 bytes;
- an **unpaired** surrogate counts as 3 bytes (the size of the U+FFFD replacement
  character).

Byte lengths for well-formed input (ASCII, valid surrogate pairs) are unchanged.

The function lives in `src/lib/isByteLength.js`.
