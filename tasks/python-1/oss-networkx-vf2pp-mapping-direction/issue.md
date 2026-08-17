# `vf2pp_isomorphism` returns the node mapping reversed

The VF2++ isomorphism helpers are documented to return a mapping **from nodes of
the first graph to nodes of the second**: `vf2pp_isomorphism(G1, G2)` should give a
dict whose keys are `G1` nodes and whose values are the corresponding `G2` nodes.

In practice the mapping comes back reversed (keys are `G2` nodes, values are `G1`
nodes):

```python
import networkx as nx
from networkx.algorithms.isomorphism import vf2pp_isomorphism

G1 = nx.path_graph(4)
G2 = nx.relabel_nodes(G1, {0: "a", 1: "b", 2: "c", 3: "d"})
vf2pp_isomorphism(G1, G2)
# returns {'a': 0, 'b': 1, ...} (G2 -> G1) instead of {0: 'a', 1: 'b', ...}
```

## Expected behavior

- `vf2pp_isomorphism(G1, G2)` returns a mapping whose **keys are `G1` nodes** and
  **values are `G2` nodes**, and that mapping is a valid isomorphism: for every
  edge `(u, v)` in `G1`, `(mapping[u], mapping[v])` is an edge in `G2`.
- `vf2pp_all_isomorphisms(G1, G2)` yields mappings in the same `G1 -> G2` direction.
- Unchanged: `vf2pp_is_isomorphic(G1, G2)` still reports whether an isomorphism
  exists, and `vf2pp_isomorphism` still returns `None` when the graphs are not
  isomorphic.

Fix the mapping direction returned by the vf2pp functions to match the documented
`G1 -> G2` contract.
