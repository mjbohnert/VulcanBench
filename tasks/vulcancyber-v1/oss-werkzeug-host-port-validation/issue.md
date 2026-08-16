# `host_is_trusted` accepts hosts with an invalid port

`host_is_trusted(hostname, trusted_list)` decides whether a request's `Host`
header matches the configured trusted hosts. It strips the port before comparing
the hostname, but it never checks that the port itself is valid. A `Host` header
such as `example.com:0`, `example.com:99999`, or `example.com:08080` is therefore
treated as trusted as long as the hostname part matches.

Accepting a malformed or out-of-range port weakens Host-header validation, which
is a guard against Host-header injection, cache poisoning, and incorrect
absolute-URL construction.

## Expected behaviour

`host_is_trusted` must reject a host whose port is not a valid TCP port:

- the port must be a decimal number in the range 1–65535;
- a port of `0`, an out-of-range port, or a port with a leading zero is invalid.

A host with a valid port, or with no port at all, is still trusted when its
hostname is in the trusted list; an untrusted hostname is still rejected.

The function lives in `src/werkzeug/sansio/utils.py`.
