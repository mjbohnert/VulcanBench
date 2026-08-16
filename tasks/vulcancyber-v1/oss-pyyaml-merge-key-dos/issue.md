# Merge keys can be expanded exponentially (denial of service)

A YAML merge key (`<<`) can reference the same anchor more than once — directly
(two `<<` entries), in a merge sequence (`<<: [*a, *a]`), or transitively when
one merged mapping itself merges another. When resolving the merge, each
referenced mapping is currently expanded **every time** it is referenced.

Because each level of nesting can re-merge the level below several times, a small
document fans out to an exponential number of merged pairs. Loading such a
document consumes unbounded CPU and memory — a denial-of-service reachable from
untrusted YAML.

## Expected behaviour

When flattening merge keys, each distinct source key node must be merged **at
most once**, regardless of how many times it is referenced (directly, through a
merge sequence, or transitively). Deduplicate by node identity so the amount of
work stays proportional to the number of distinct keys rather than the number of
references.

Ordinary, non-duplicated merges must be unaffected: a single `<<` still
contributes all of its keys, and the loaded result is unchanged.

The relevant code is the merge handling in `lib/yaml/constructor.py`
(`flatten_mapping`).
