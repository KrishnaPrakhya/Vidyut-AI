from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandapower as pp

from services.sim.domain import DistributionTransformer, TieSwitch

FEEDER_IDS = ["F1", "F2", "F3"]
DTS_PER_FEEDER = 20
SUB_VN_KV = 11.0
LV_VN_KV = 0.415
MV_LINE_STD_TYPE = "NA2XS2Y 1x70 RM/25 6/10 kV"
STANDARD_DT_RATINGS_KVA = [63.0, 100.0, 160.0, 200.0, 250.0, 315.0, 400.0, 500.0]
PROVISIONAL_DT_RATING_KVA = 160.0
POWER_FACTOR = 0.95


def _trafo_pfe_kw(rating_kva: float) -> float:
    return 0.6 * (rating_kva / 250.0)


@dataclass
class NetworkContext:
    net: pp.pandapowerNet
    sub_bus: int
    dt_ids: list[str]
    feeder_of_dt: dict[str, str]
    dt_ids_of_feeder: dict[str, list[str]]
    dt_mv_bus: dict[str, int]
    dt_lv_bus: dict[str, int]
    dt_trafo_idx: dict[str, int]
    dt_load_idx: dict[str, int]
    dt_section_switch: dict[str, int]
    dt_section_line: dict[str, int]
    dt_parent: dict[str, str | None]
    dts: dict[str, DistributionTransformer]
    tie_switches: dict[str, TieSwitch]
    tie_switch_pp_idx: dict[str, int]
    tie_switch_bus: dict[str, tuple[int, int]]
    switch_graph: Any | None = field(default=None, repr=False)


def _recursive_tree_parents(n: int, rng: np.random.Generator) -> list[int]:
    parents = [-1]
    for i in range(1, n):
        parents.append(int(rng.integers(0, i)))
    return parents


def _depths(parents: list[int]) -> list[int]:
    depths = [0] * len(parents)
    for i in range(1, len(parents)):
        depths[i] = depths[parents[i]] + 1
    return depths


def build_network(rng: np.random.Generator) -> NetworkContext:
    net = pp.create_empty_network(f_hz=50.0, sn_mva=1.0)
    sub_bus = pp.create_bus(net, vn_kv=SUB_VN_KV, name="SUB")
    pp.create_ext_grid(net, bus=sub_bus, vm_pu=1.02, name="GRID")

    dt_ids: list[str] = []
    feeder_of_dt: dict[str, str] = {}
    dt_ids_of_feeder: dict[str, list[str]] = {}
    dt_mv_bus: dict[str, int] = {}
    dt_lv_bus: dict[str, int] = {}
    dt_trafo_idx: dict[str, int] = {}
    dt_load_idx: dict[str, int] = {}
    dt_section_switch: dict[str, int] = {}
    dt_section_line: dict[str, int] = {}
    dt_parent: dict[str, str | None] = {}
    dts: dict[str, DistributionTransformer] = {}
    leaf_of_feeder: dict[str, str] = {}

    for feeder_id in FEEDER_IDS:
        parents = _recursive_tree_parents(DTS_PER_FEEDER, rng)
        depths = _depths(parents)
        feeder_dt_ids = [f"{feeder_id}-DT{k + 1:02d}" for k in range(DTS_PER_FEEDER)]
        dt_ids_of_feeder[feeder_id] = feeder_dt_ids

        for k, dt_id in enumerate(feeder_dt_ids):
            dt_ids.append(dt_id)
            feeder_of_dt[dt_id] = feeder_id
            mv_bus = pp.create_bus(net, vn_kv=SUB_VN_KV, name=f"{dt_id}-MV")
            lv_bus = pp.create_bus(net, vn_kv=LV_VN_KV, name=f"{dt_id}-LV")
            dt_mv_bus[dt_id] = mv_bus
            dt_lv_bus[dt_id] = lv_bus

            parent_idx = parents[k]
            parent_dt_id = feeder_dt_ids[parent_idx] if parent_idx >= 0 else None
            dt_parent[dt_id] = parent_dt_id
            from_bus = dt_mv_bus[parent_dt_id] if parent_dt_id else sub_bus

            length_km = float(rng.uniform(0.3, 1.0))
            line_idx = pp.create_line(
                net, from_bus=from_bus, to_bus=mv_bus, length_km=length_km,
                std_type=MV_LINE_STD_TYPE, name=f"{dt_id}-trunk",
            )
            switch_idx = pp.create_switch(
                net, bus=from_bus, element=line_idx, et="l", closed=True, name=f"SEC-{dt_id}",
            )
            dt_section_line[dt_id] = line_idx
            dt_section_switch[dt_id] = switch_idx

            rating_kva = PROVISIONAL_DT_RATING_KVA
            trafo_idx = pp.create_transformer_from_parameters(
                net, hv_bus=mv_bus, lv_bus=lv_bus,
                sn_mva=rating_kva / 1000.0, vn_hv_kv=SUB_VN_KV, vn_lv_kv=LV_VN_KV,
                vkr_percent=1.2, vk_percent=4.0, pfe_kw=_trafo_pfe_kw(rating_kva),
                i0_percent=0.24, shift_degree=150.0, name=dt_id,
            )
            dt_trafo_idx[dt_id] = trafo_idx

            load_idx = pp.create_load(net, bus=lv_bus, p_mw=0.0, q_mvar=0.0, name=dt_id)
            dt_load_idx[dt_id] = load_idx

            dts[dt_id] = DistributionTransformer(id=dt_id, feeder_id=feeder_id, rating_kva=rating_kva)

        deepest_k = int(np.argmax(depths))
        leaf_of_feeder[feeder_id] = feeder_dt_ids[deepest_k]

    tie_switches: dict[str, TieSwitch] = {}
    tie_switch_pp_idx: dict[str, int] = {}
    tie_switch_bus: dict[str, tuple[int, int]] = {}
    tie_pairs = [("TS-F1-F2", "F1", "F2"), ("TS-F2-F3", "F2", "F3"), ("TS-F1-F3", "F1", "F3")]
    for ts_id, fa, fb in tie_pairs:
        dt_a = leaf_of_feeder[fa]
        dt_b = leaf_of_feeder[fb]
        bus_a = dt_mv_bus[dt_a]
        bus_b = dt_mv_bus[dt_b]
        switch_idx = pp.create_switch(net, bus=bus_a, element=bus_b, et="b", closed=False, name=ts_id)
        tie_switches[ts_id] = TieSwitch(id=ts_id, bus_a=dt_a, bus_b=dt_b, closed=False)
        tie_switch_pp_idx[ts_id] = switch_idx
        tie_switch_bus[ts_id] = (bus_a, bus_b)

    return NetworkContext(
        net=net, sub_bus=sub_bus, dt_ids=dt_ids, feeder_of_dt=feeder_of_dt,
        dt_ids_of_feeder=dt_ids_of_feeder, dt_mv_bus=dt_mv_bus, dt_lv_bus=dt_lv_bus,
        dt_trafo_idx=dt_trafo_idx, dt_load_idx=dt_load_idx,
        dt_section_switch=dt_section_switch, dt_section_line=dt_section_line,
        dt_parent=dt_parent, dts=dts, tie_switches=tie_switches,
        tie_switch_pp_idx=tie_switch_pp_idx, tie_switch_bus=tie_switch_bus,
    )


def resize_transformers(
    ctx: NetworkContext, design_peak_kw: dict[str, float], rng: np.random.Generator
) -> None:
    ratings = np.array(STANDARD_DT_RATINGS_KVA)
    for dt_id, peak_kw in design_peak_kw.items():
        design_utilisation = float(np.clip(rng.normal(0.78, 0.10), 0.55, 0.95))
        required_kva = peak_kw / POWER_FACTOR / design_utilisation
        eligible = ratings[ratings >= required_kva]
        rating_kva = float(eligible[0]) if eligible.size else float(ratings[-1])

        ctx.dts[dt_id].rating_kva = rating_kva
        trafo_idx = ctx.dt_trafo_idx[dt_id]
        ctx.net.trafo.at[trafo_idx, "sn_mva"] = rating_kva / 1000.0
        ctx.net.trafo.at[trafo_idx, "pfe_kw"] = _trafo_pfe_kw(rating_kva)


def set_dt_load_kw(ctx: NetworkContext, dt_id: str, p_kw: float) -> None:
    load_idx = ctx.dt_load_idx[dt_id]
    p_mw = p_kw / 1000.0
    q_mvar = p_mw * math.tan(math.acos(POWER_FACTOR))
    ctx.net.load.at[load_idx, "p_mw"] = p_mw
    ctx.net.load.at[load_idx, "q_mvar"] = q_mvar
