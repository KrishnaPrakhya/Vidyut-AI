from __future__ import annotations

from dataclasses import dataclass, field

from services.sim.controllers.base import ControllerState, ReasonCode, TickEvent
from services.sim.world import PowerFlowResult, World

OVERLOAD_PCT = 100.0
TRIP_AFTER_CONSECUTIVE_TICKS = 2
DE_ENERGISE_TICKS = 3


@dataclass
class BaselineController:
    name: str = "baseline"
    state: ControllerState = field(default_factory=ControllerState)
    consecutive_overload: dict[str, int] = field(default_factory=dict)

    def before_tick(self, world: World, tick: int) -> list[TickEvent]:
        self._restore_expired(world, tick)
        return self.state.drain()

    def act(self, world: World, tick: int, result: PowerFlowResult) -> list[TickEvent]:
        if result.converged:
            self._trip_overloaded(world, tick, result)

        return self.state.drain()

    def _restore_expired(self, world: World, tick: int) -> None:
        for dt_id, restore_tick in list(world.dt_reenergize_tick.items()):
            if tick < restore_tick:
                continue
            del world.dt_reenergize_tick[dt_id]
            self.consecutive_overload[dt_id] = 0
            self.state.emit(
                tier=0,
                action="dt_restore",
                target=dt_id,
                kw=0.0,
                households=len(world.ctx.dts[dt_id].households),
                reason_code=ReasonCode.BASELINE_RESTORE,
                detail=f"{dt_id} re-energised after {DE_ENERGISE_TICKS * 15} minutes",
            )

    def _trip_overloaded(self, world: World, tick: int, result: PowerFlowResult) -> None:
        for dt_id in world.dt_ids:
            if not world.dt_energized[dt_id]:
                continue
            if dt_id in world.dt_reenergize_tick:
                continue

            loading = float(result.trafo_loading_pct[world.ctx.dt_trafo_idx[dt_id]])
            if loading <= OVERLOAD_PCT:
                self.consecutive_overload[dt_id] = 0
                continue

            self.consecutive_overload[dt_id] = self.consecutive_overload.get(dt_id, 0) + 1
            if self.consecutive_overload[dt_id] < TRIP_AFTER_CONSECUTIVE_TICKS:
                continue

            households = world.ctx.dts[dt_id].households
            start_tick = tick + 1
            end_tick = min(start_tick + DE_ENERGISE_TICKS, world.simulation_ticks)
            if end_tick <= start_tick:
                continue
            minutes = (end_tick - start_tick) * 15.0
            world.scheduled_outages.setdefault(dt_id, []).append((start_tick, end_tick))
            world.dt_reenergize_tick[dt_id] = end_tick
            self.consecutive_overload[dt_id] = 0

            for hh_id in households:
                world.ledger.charge(
                    tick=tick,
                    household_id=hh_id,
                    dt_id=dt_id,
                    level="disconnect",
                    kw=0.0,
                    minutes=minutes,
                    reason_code=ReasonCode.BASELINE_DT_OVERLOAD,
                )

            self.state.emit(
                tier=0,
                action="dt_de_energise",
                target=dt_id,
                kw=0.0,
                households=len(households),
                reason_code=ReasonCode.BASELINE_DT_OVERLOAD,
                detail=(
                    f"{dt_id} at {loading:.0f}% for {TRIP_AFTER_CONSECUTIVE_TICKS} consecutive "
                    f"intervals, de-energised for {minutes:.0f} minutes"
                ),
            )
