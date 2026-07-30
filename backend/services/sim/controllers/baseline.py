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

    def act(self, world: World, tick: int, result: PowerFlowResult) -> list[TickEvent]:
        self._restore_expired(world, tick)

        if result.converged:
            self._trip_overloaded(world, tick, result)

        return self.state.drain()

    def _restore_expired(self, world: World, tick: int) -> None:
        for dt_id, restore_tick in list(world.dt_reenergize_tick.items()):
            if tick < restore_tick:
                continue
            world.dt_energized[dt_id] = True
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

            loading = float(result.trafo_loading_pct[world.ctx.dt_trafo_idx[dt_id]])
            if loading <= OVERLOAD_PCT:
                self.consecutive_overload[dt_id] = 0
                continue

            self.consecutive_overload[dt_id] = self.consecutive_overload.get(dt_id, 0) + 1
            if self.consecutive_overload[dt_id] < TRIP_AFTER_CONSECUTIVE_TICKS:
                continue

            households = world.ctx.dts[dt_id].households
            world.dt_energized[dt_id] = False
            world.dt_reenergize_tick[dt_id] = tick + 1 + DE_ENERGISE_TICKS
            self.consecutive_overload[dt_id] = 0

            for hh_id in households:
                world.ledger.charge(
                    tick=tick,
                    household_id=hh_id,
                    dt_id=dt_id,
                    level="disconnect",
                    kw=0.0,
                    minutes=DE_ENERGISE_TICKS * 15.0,
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
                    f"intervals, de-energised for {DE_ENERGISE_TICKS * 15} minutes"
                ),
            )
