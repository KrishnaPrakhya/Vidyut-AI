from __future__ import annotations

import numpy as np

from services.sim.reconfiguration import (
    MAX_LOADING_PCT,
    VM_MAX_PU,
    VM_MIN_PU,
    _candidate_pairs,
    evaluate_reconfiguration,
)
from services.sim.topology import is_radial, switches_in_loop
from services.sim.world import apply_loads, build_world, solve_power_flow


def _world_at_peak(tick: int = 76):
    world = build_world("vidyut", "heatwave", 42)
    apply_loads(world, tick)
    return world, solve_power_flow(world)


def test_network_starts_radial() -> None:
    world = build_world("vidyut", "heatwave", 42)
    assert is_radial(world.ctx)


def test_closing_a_tie_switch_alone_breaks_radiality() -> None:
    world = build_world("vidyut", "heatwave", 42)
    switch_idx = next(iter(world.ctx.tie_switch_pp_idx.values()))
    world.ctx.net.switch.at[switch_idx, "closed"] = True
    assert not is_radial(world.ctx)


def test_opening_any_loop_switch_restores_radiality() -> None:
    world = build_world("vidyut", "heatwave", 42)
    for ts_id, switch_idx in world.ctx.tie_switch_pp_idx.items():
        loop = switches_in_loop(world.ctx, ts_id)
        world.ctx.net.switch.at[switch_idx, "closed"] = True
        for open_switch in loop:
            world.ctx.net.switch.at[open_switch, "closed"] = False
            assert is_radial(world.ctx)
            world.ctx.net.switch.at[open_switch, "closed"] = True
        world.ctx.net.switch.at[switch_idx, "closed"] = False


def test_every_candidate_pair_is_radial_when_applied() -> None:
    world, _ = _world_at_peak()
    for pair in _candidate_pairs(world):
        world.ctx.net.switch.at[pair.close_switch, "closed"] = True
        world.ctx.net.switch.at[pair.open_switch, "closed"] = False
        assert is_radial(world.ctx)
        world.ctx.net.switch.at[pair.close_switch, "closed"] = False
        world.ctx.net.switch.at[pair.open_switch, "closed"] = True


def test_selected_candidate_satisfies_all_constraints() -> None:
    world, result = _world_at_peak()
    candidate = evaluate_reconfiguration(world, result)
    if candidate is None:
        return

    assert candidate.result.converged
    assert candidate.result.vm_pu_min >= VM_MIN_PU
    assert candidate.result.vm_pu_max <= VM_MAX_PU
    assert float(np.nanmax(candidate.result.line_loading_pct)) <= MAX_LOADING_PCT


def test_evaluation_leaves_switch_state_untouched() -> None:
    world, result = _world_at_peak()
    before = world.ctx.net.switch["closed"].copy()
    evaluate_reconfiguration(world, result)
    assert (world.ctx.net.switch["closed"] == before).all()


def test_non_convergent_state_yields_no_candidate() -> None:
    world, result = _world_at_peak()
    result.converged = False
    assert evaluate_reconfiguration(world, result) is None
