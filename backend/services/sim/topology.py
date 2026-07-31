from __future__ import annotations

import networkx as nx

from services.sim.network import NetworkContext


def _build_switch_graph(ctx: NetworkContext) -> nx.Graph:
    if ctx.switch_graph is not None:
        return ctx.switch_graph
    graph = nx.Graph()
    graph.add_nodes_from(ctx.net.bus.index)
    for dt_id, line_idx in ctx.dt_section_line.items():
        line = ctx.net.line.loc[line_idx]
        switch_idx = ctx.dt_section_switch[dt_id]
        graph.add_edge(int(line.from_bus), int(line.to_bus), switch_idx=switch_idx)
    for ts_id, (bus_a, bus_b) in ctx.tie_switch_bus.items():
        graph.add_edge(bus_a, bus_b, switch_idx=ctx.tie_switch_pp_idx[ts_id])
    ctx.switch_graph = graph
    return graph


def _closed_subgraph(ctx: NetworkContext, graph: nx.Graph) -> nx.Graph:
    closed = ctx.net.switch.closed
    edges = [
        (u, v) for u, v, d in graph.edges(data=True) if bool(closed.at[d["switch_idx"]])
    ]
    sub = nx.Graph()
    sub.add_nodes_from(graph.nodes)
    sub.add_edges_from(edges)
    return sub


def is_radial(ctx: NetworkContext) -> bool:
    graph = _build_switch_graph(ctx)
    sub = _closed_subgraph(ctx, graph)
    mv_buses = [ctx.sub_bus] + list(ctx.dt_mv_bus.values())
    reachable = nx.node_connected_component(sub, ctx.sub_bus)
    if not set(mv_buses).issubset(reachable):
        return False
    induced = sub.subgraph(mv_buses)
    return nx.is_tree(induced)


def switches_in_loop(ctx: NetworkContext, tie_switch_id: str) -> list[int]:
    graph = _build_switch_graph(ctx)
    sub = _closed_subgraph(ctx, graph)
    bus_a, bus_b = ctx.tie_switch_bus[tie_switch_id]
    path = nx.shortest_path(sub, bus_a, bus_b)
    switch_ids = []
    for u, v in zip(path[:-1], path[1:]):
        switch_ids.append(graph.edges[u, v]["switch_idx"])
    return switch_ids
