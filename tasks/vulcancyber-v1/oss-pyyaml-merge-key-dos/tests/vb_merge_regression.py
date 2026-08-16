# Hidden pass_to_pass regression guard for oss-pyyaml-merge-key-dos.
#
# Deduplicating repeated merge nodes must not change the result of ordinary merges:
# a single (non-duplicated) merge still contributes all of its keys, and the public
# safe_load of a merged mapping still produces the correct dict. Both hold at the
# base commit and after the fix.

import yaml

from vb_merge_dos import flatten_mapping_keys


def test_single_merge_still_contributes_all_keys():
    keys = flatten_mapping_keys(
        "base: &base {x: 1, y: 2}\n"
        "target:\n"
        "  <<: *base\n"
        "  z: 3\n",
        "target",
        yaml.SafeLoader,
    )
    assert keys == ["x", "y", "z"]


def test_public_safe_load_merge_result_is_correct():
    doc = yaml.safe_load(
        "base: &base {x: 1, y: 2}\n"
        "merged:\n"
        "  <<: *base\n"
        "  y: 20\n"
        "  z: 3\n"
    )
    assert doc["merged"] == {"x": 1, "y": 20, "z": 3}
