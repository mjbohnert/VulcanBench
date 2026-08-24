"""Hidden behavioral tests for oss-networkx-vf2pp-mapping-direction (#8813).

``vf2pp_isomorphism(G1, G2)`` documents its return value as a mapping from nodes of
G1 to nodes of G2. The implementation returned it reversed (G2 -> G1). Graded on the
public vf2pp API: the mapping's direction and its validity as an isomorphism.
"""

from __future__ import annotations

import networkx as nx
from networkx.algorithms.isomorphism import (
    vf2pp_all_isomorphisms,
    vf2pp_is_isomorphic,
    vf2pp_isomorphism,
)


def _relabelled(g: nx.Graph, offset: int = 100) -> nx.Graph:
    return nx.relabel_nodes(g, {n: n + offset for n in g})


# --- fail_to_pass: the mapping came back reversed at the base commit ----------


def test_mapping_keys_are_g1_values_are_g2() -> None:
    g1 = nx.path_graph(5)
    g2 = nx.relabel_nodes(g1, {i: f"n{i}" for i in g1})
    m = vf2pp_isomorphism(g1, g2)
    assert m is not None
    assert set(m.keys()) == set(g1.nodes())
    assert set(m.values()) == set(g2.nodes())


def test_mapping_is_a_valid_g1_to_g2_isomorphism() -> None:
    g1 = nx.cycle_graph(6)
    g2 = _relabelled(g1)
    m = vf2pp_isomorphism(g1, g2)
    assert m is not None
    assert set(m.keys()) == set(g1.nodes())
    for u, v in g1.edges():
        assert g2.has_edge(m[u], m[v])


def test_all_isomorphisms_have_g1_to_g2_direction() -> None:
    g1 = nx.cycle_graph(6)
    g2 = _relabelled(g1)
    for m in vf2pp_all_isomorphisms(g1, g2):
        assert set(m.keys()) == set(g1.nodes())
        assert set(m.values()) == set(g2.nodes())


# --- pass_to_pass: direction-independent behavior is unchanged ----------------


def test_is_isomorphic_still_true() -> None:
    g1 = nx.cycle_graph(6)
    g2 = _relabelled(g1)
    assert vf2pp_is_isomorphic(g1, g2) is True


def test_non_isomorphic_returns_none() -> None:
    g1 = nx.cycle_graph(6)
    g2 = nx.path_graph(6)  # not isomorphic to a cycle
    assert vf2pp_isomorphism(g1, g2) is None
