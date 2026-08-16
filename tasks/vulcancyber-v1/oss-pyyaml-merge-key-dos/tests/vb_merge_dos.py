# Hidden fail_to_pass tests for oss-pyyaml-merge-key-dos (yaml/pyyaml PR #937).
#
# A YAML merge key (`<<`) that references the same anchor more than once — directly,
# in a merge sequence, or transitively through nested merges — used to be expanded
# once per reference. Because each level can re-merge the level below several times,
# a small document fans out to an exponential number of merged pairs: a
# denial-of-service (unbounded CPU/memory) while resolving the merge.
#
# The fix deduplicates merged key nodes by identity in Loader.flatten_mapping, so
# each distinct source key is merged at most once. These tests assert the merged
# key list is deduplicated. The intermediate flatten_mapping result is where the
# blow-up happens (the final dict collapses duplicate keys, hiding it), so the tests
# inspect flatten_mapping directly, exactly as the upstream regression test does.

import yaml


def flatten_mapping_keys(source, name, Loader):
    loader = Loader(source)
    try:
        root = loader.get_single_node()
        for key_node, value_node in root.value:
            if key_node.value == name:
                loader.flatten_mapping(value_node)
                return [k.value for k, v in value_node.value]
        raise AssertionError("mapping %r was not found" % name)
    finally:
        loader.dispose()


def merge_fanout_source(levels, width):
    lines = [
        "n0: &n0 {%s}" % ", ".join("k%s: %s" % (i, i) for i in range(width))
    ]
    previous = "n0"
    for level in range(1, levels + 1):
        prefix = chr(ord("a") + level - 1)
        aliases = []
        for i in range(width):
            name = "%s%s" % (prefix, i)
            lines.append("%s: &%s {<<: *%s}" % (name, name, previous))
            aliases.append("*%s" % name)
        current = "n%s" % level
        lines.append("%s: &%s {<<: [%s]}" % (current, current, ",".join(aliases)))
        previous = current
    lines.append("root: {<<: *%s}" % previous)
    return "\n".join(lines)


def test_duplicate_sequence_merge_nodes_are_skipped():
    keys = flatten_mapping_keys(
        "base: &base {x: 1, y: 2}\n"
        "target:\n"
        "  <<: [*base, *base]\n"
        "  z: 3\n",
        "target",
        yaml.SafeLoader,
    )
    assert keys == ["x", "y", "z"]


def test_duplicate_direct_merge_nodes_are_skipped():
    keys = flatten_mapping_keys(
        "base: &base {x: 1, y: 2}\n"
        "target:\n"
        "  <<: *base\n"
        "  <<: *base\n"
        "  z: 3\n",
        "target",
        yaml.SafeLoader,
    )
    assert keys == ["x", "y", "z"]


def test_fanout_merge_keys_are_deduplicated():
    # Without dedup this fans out exponentially; with the fix it is exactly the
    # width-many distinct base keys plus nothing else.
    keys = flatten_mapping_keys(merge_fanout_source(levels=4, width=4), "root", yaml.SafeLoader)
    assert keys == ["k0", "k1", "k2", "k3"]
