"""Wikilink graph construction and deterministic community detection.

Shared by ariadne-graph and ariadne-similar, which both need the same undirected
adjacency map.

Louvain rather than label propagation because it yields a modularity score: the
real vault is deliberately never measured during development, so the tools
cannot be tuned against known numbers and must instead report the shape they
found for the reader to judge.

Every node ordering in here is sorted, so the same vault always produces the
same clusters with the same ids across runs.
"""

import sys

import ariadne_common


def adjacency_from_links(entries, name_index):
    """Adjacency for callers that already read the notes.

    Each entry needs a "path" and its raw "links". Links to notes outside the
    scanned set, and a note's links to itself, are not edges.
    """
    neighbors = {entry["path"]: set() for entry in entries}
    for entry in entries:
        path = entry["path"]
        for link_text in entry["links"]:
            target = ariadne_common.resolve_link(link_text, name_index)
            if target is not None and target != path and target in neighbors:
                neighbors[path].add(target)
                neighbors[target].add(path)
    return neighbors


def build_graph(files, name_index):
    """Read every note, then resolve its links: {path: {neighbors, broken_links}}."""
    entries = []
    broken = {path: [] for path in files}
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as exc:
            print(
                f"warning: skipping unreadable note {ariadne_common.printable(path)}: "
                f"{ariadne_common.printable(exc)}",
                file=sys.stderr,
            )
            entries.append({"path": path, "links": []})
            continue
        links = ariadne_common.extract_links(text)
        entries.append({"path": path, "links": links})
        broken[path] = [
            link for link in links if ariadne_common.resolve_link(link, name_index) is None
        ]
    neighbors = adjacency_from_links(entries, name_index)
    return {path: {"neighbors": neighbors[path], "broken_links": broken[path]} for path in files}


def adjacency(graph):
    """The plain {path: set(path)} map community detection consumes."""
    return {path: set(entry["neighbors"]) for path, entry in graph.items()}


def cluster_entry_points(neighbors, labels):
    """Per cluster: the note reaching most of it, and what share that is.

    `coverage` answers "is there a way into this group?" — the fraction of a
    cluster's other notes reachable in one hop from its best-connected member.
    A map of content scores 1.0 because it links to everything it indexes.

    The measure is deliberately scale-sensitive: a small cluster cannot help but
    have high coverage, so only groups too large for any one note to index score
    low. That is what keeps a missing-hub report from flooding with three-note
    clusters that need no map of content. A one-note cluster scores 1.0 by
    convention — it is trivially its own entry point, and orphan detection
    already covers it.
    """
    members = {}
    for node, cluster_id in labels.items():
        members.setdefault(cluster_id, []).append(node)
    report = []
    for cluster_id, group in members.items():
        group = sorted(group)
        inside = set(group)
        # Ties are common — every member of a ring reaches the same number — so
        # `entry_point` is the first of the best, not necessarily a standout.
        best, reach = group[0], 0
        for node in group:
            hit = len(neighbors.get(node, set()) & inside)
            if hit > reach:
                best, reach = node, hit
        others = len(group) - 1
        report.append(
            {
                "cluster": cluster_id,
                "size": len(group),
                "entry_point": best,
                "reach": reach,
                "others": others,
                "coverage": round(reach / others, 4) if others else 1.0,
            }
        )
    report.sort(key=lambda c: (-c["size"], c["cluster"]))
    return report


def components(neighbors):
    """Connected components, each a sorted node list. Largest first, then alphabetical."""
    seen = set()
    found = []
    for node in sorted(neighbors):
        if node in seen:
            continue
        seen.add(node)
        stack = [node]
        group = []
        while stack:
            current = stack.pop()
            group.append(current)
            for other in sorted(neighbors.get(current, ())):
                if other in neighbors and other not in seen:
                    seen.add(other)
                    stack.append(other)
        found.append(sorted(group))
    found.sort(key=lambda group: (-len(group), group[0]))
    return found


def _index_graph(neighbors):
    """Relabel nodes to 0..n-1 in sorted order, so later levels can compare ids."""
    nodes = sorted(neighbors)
    index = {node: i for i, node in enumerate(nodes)}
    adj = {i: {} for i in range(len(nodes))}
    for node in nodes:
        u = index[node]
        for other in sorted(neighbors[node]):
            v = index.get(other)
            if v is not None and v != u:
                # Symmetrised here rather than trusted: louvain(), modularity() and
                # shape() are public and take a raw neighbour map, and a one-way edge
                # would otherwise survive to _aggregate's half-edge guard and vanish.
                adj[u][v] = 1.0
                adj[v][u] = 1.0
    return nodes, index, adj, {u: 0.0 for u in adj}


def _degrees(adj, loops):
    """Weighted degree, counting a self-loop at both of its ends."""
    return {u: sum(adj[u].values()) + 2 * loops[u] for u in adj}


def _modularity(adj, loops, community):
    degrees = _degrees(adj, loops)
    total = sum(degrees.values())  # 2m
    if total == 0:
        return 0.0
    inner = {}
    tot = {}
    for u in adj:
        c = community[u]
        tot[c] = tot.get(c, 0.0) + degrees[u]
        inner[c] = inner.get(c, 0.0) + 2 * loops[u]
        for v, weight in adj[u].items():
            if community[v] == c:
                inner[c] += weight
    return sum(inner[c] / total - (tot[c] / total) ** 2 for c in tot)


def _local_moving(adj, loops):
    """One Louvain level: move each node to the neighbouring community it most improves."""
    degrees = _degrees(adj, loops)
    total = sum(degrees.values())
    community = {u: u for u in adj}
    if total == 0:
        return community
    tot = dict(degrees)
    improved = True
    passes = 0
    # Equal-gain moves always go to a smaller community id, so the plateau cannot
    # cycle in exact arithmetic. The cap makes a float edge case cost a slightly
    # worse partition rather than a hung editor picker.
    while improved and passes < len(adj):
        passes += 1
        improved = False
        for u in sorted(adj):
            own = community[u]
            weights = {}
            for v, weight in adj[u].items():
                weights[community[v]] = weights.get(community[v], 0.0) + weight
            # Remove u from its community before scoring, so staying put competes
            # on the same footing and scores exactly 0 when u is already alone.
            tot[own] -= degrees[u]
            candidates = [(weights.get(own, 0.0) - tot[own] * degrees[u] / total, -own)]
            for c in sorted(weights):
                if c != own:
                    candidates.append((weights[c] - tot[c] * degrees[u] / total, -c))
            _, negated = max(candidates)
            best = -negated
            tot[best] += degrees[u]
            if best != own:
                community[u] = best
                improved = True
    return community


def _aggregate(adj, loops, community):
    """Collapse each community into one node, preserving total edge weight."""
    labels = {c: i for i, c in enumerate(sorted(set(community.values())))}
    new_adj = {i: {} for i in labels.values()}
    new_loops = {i: 0.0 for i in labels.values()}
    for u in sorted(adj):
        cu = labels[community[u]]
        new_loops[cu] += loops[u]
        for v, weight in adj[u].items():
            if v <= u:  # each undirected edge once
                continue
            cv = labels[community[v]]
            if cu == cv:
                new_loops[cu] += weight
            else:
                new_adj[cu][cv] = new_adj[cu].get(cv, 0.0) + weight
                new_adj[cv][cu] = new_adj[cv].get(cu, 0.0) + weight
    return new_adj, new_loops


def louvain(neighbors):
    """Community id per node. Isolated notes each get their own cluster."""
    nodes, _, adj, loops = _index_graph(neighbors)
    if not nodes:
        return {}
    assignment = {u: u for u in adj}
    while True:
        community = _local_moving(adj, loops)
        if len(set(community.values())) == len(adj):
            break  # nothing merged, so no further level can help
        labels = {c: i for i, c in enumerate(sorted(set(community.values())))}
        assignment = {u: labels[community[assignment[u]]] for u in assignment}
        adj, loops = _aggregate(adj, loops, community)

    # Renumber by first member, so ids don't depend on how many levels ran.
    order = {}
    for u in sorted(assignment):
        order.setdefault(assignment[u], len(order))
    return {nodes[u]: order[assignment[u]] for u in assignment}


def modularity(neighbors, labels):
    """How much better the partition is than chance: ~0 is no structure, 0.3+ is real."""
    _, index, adj, loops = _index_graph(neighbors)
    if not adj:
        return 0.0
    return _modularity(adj, loops, {index[node]: labels[node] for node in index})


def shape(neighbors, labels):
    """Graph statistics the tools print alongside results, as their own caveat.

    Hundreds of tiny components, or a modularity near zero, means the cluster
    columns are noise and should be ignored.
    """
    groups = components(neighbors)
    sizes = {}
    for cluster_id in labels.values():
        sizes[cluster_id] = sizes.get(cluster_id, 0) + 1
    return {
        "notes": len(neighbors),
        "edges": sum(len(n) for n in neighbors.values()) // 2,
        "components": len(groups),
        "largest_component": len(groups[0]) if groups else 0,
        "isolated": sum(1 for group in groups if len(group) == 1),
        "clusters": len(sizes),
        "largest_cluster": max(sizes.values()) if sizes else 0,
        "modularity": round(modularity(neighbors, labels), 4),
    }


def describe_shape(summary):
    """shape() as a single line for a text report."""
    return (
        f"graph: {summary['notes']} notes, {summary['edges']} links, "
        f"{summary['components']} components (largest {summary['largest_component']}, "
        f"{summary['isolated']} isolated) — {summary['clusters']} clusters, "
        f"modularity {summary['modularity']:.3f}"
    )
