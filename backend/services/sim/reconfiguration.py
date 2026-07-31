from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from services.sim.topology import switches_in_loop
from services.sim.world import PowerFlowResult, World, solve_power_flow

VM_MIN_PU = 0.95
VM_MAX_PU = 1.05
MAX_LOADING_PCT = 100.0

W_LOSSES = 0.30
W_MAX_LOADING = 0.50
W_SPREAD = 0.20

IMPROVEMENT_MARGIN = 0.005


@dataclass
class SwitchPair:
    tie_switch_id: str
    close_switch: int
    open_switch: int


@dataclass
class ReconfigCandidate:
    pair: SwitchPair
    score: float
    result: PowerFlowResult


def objective(result: PowerFlowResult) -> float:
    """Baran & Wu (1989) style objective: loss reduction plus load balancing."""
    loadings = list(result.feeder_loading_pct.values())
    spread = max(loadings) - min(loadings)
    max_loading = max(
        float(np.nanmax(result.trafo_loading_pct)),
        float(np.nanmax(result.line_loading_pct)),
    )
    return (
        W_LOSSES * (result.losses_kw / 100.0)
        + W_MAX_LOADING * (max_loading / 100.0)
        + W_SPREAD * (spread / 100.0)
    )


def _feasible(result: PowerFlowResult) -> bool:
    if not result.converged:
        return False
    if result.vm_pu_min < VM_MIN_PU or result.vm_pu_max > VM_MAX_PU:
        return False
    if float(np.nanmax(result.line_loading_pct)) > MAX_LOADING_PCT:
        return False
    if float(np.nanmax(result.trafo_loading_pct)) > MAX_LOADING_PCT:
        return False
    return True


def _candidate_pairs(world: World) -> list[SwitchPair]:
    pairs: list[SwitchPair] = []
    for ts_id, tie in world.ctx.tie_switches.items():
        if tie.closed:
            continue
        close_switch = world.ctx.tie_switch_pp_idx[ts_id]
        loop = switches_in_loop(world.ctx, ts_id)
        for open_switch in loop:
            if open_switch == close_switch:
                continue
            pairs.append(SwitchPair(ts_id, close_switch, open_switch))
    return pairs


def _set_switches(world: World, states: dict[int, bool]) -> None:
    for switch_idx, closed in states.items():
        world.ctx.net.switch.at[switch_idx, "closed"] = closed


def evaluate_reconfiguration(world: World, current: PowerFlowResult) -> ReconfigCandidate | None:
    if not current.converged:
        return None

    current_score = objective(current)
    best: ReconfigCandidate | None = None

    for pair in _candidate_pairs(world):
        original = {
            pair.close_switch: bool(world.ctx.net.switch.at[pair.close_switch, "closed"]),
            pair.open_switch: bool(world.ctx.net.switch.at[pair.open_switch, "closed"]),
        }
        _set_switches(world, {pair.close_switch: True, pair.open_switch: False})

        result = solve_power_flow(world)
        if _feasible(result):
            score = objective(result)
            if best is None or score < best.score:
                best = ReconfigCandidate(pair=pair, score=score, result=result)

        _set_switches(world, original)

    if best is None or best.score > current_score - IMPROVEMENT_MARGIN:
        return None
    return best


def apply_reconfiguration(world: World, candidate: ReconfigCandidate) -> None:
    _set_switches(
        world, {candidate.pair.close_switch: True, candidate.pair.open_switch: False}
    )
    world.ctx.tie_switches[candidate.pair.tie_switch_id].closed = True
