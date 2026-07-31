from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from services.actuation.commands import ActuationCommand
from services.dispatch.outbox import Notification, Outbox, clock_of
from services.forecast.base import Forecaster
from services.sim.controllers.base import ControllerState, ReasonCode, TickEvent
from services.sim.demand import TICK_MINUTES
from services.sim.reconfiguration import apply_reconfiguration, evaluate_reconfiguration
from services.sim.scenario import N_TICKS
from services.sim.world import PowerFlowResult, World

DEBT_WEIGHT = 3.0
CURTAIL_COOLDOWN_TICKS = 8
FORECAST_HORIZON = 4
SHIFT_HORIZON = 8
DEVICE_CURTAIL_TICKS = 2
LOAD_LIMIT_TICKS = 2
DISCONNECT_TICKS = 2
LOAD_LIMIT_REDUCTION_FRACTION = 0.35
RECONFIG_INTERVAL_TICKS = 4
RECONFIG_TRIGGER_SPREAD_PCT = 8.0
RECONFIG_TRIGGER_LOADING_PCT = 85.0
EMERGENCY_LOADING_PCT = 100.0
PRICE_SIGNAL_TICKS = 4
PRICE_SIGNAL_COOLDOWN_TICKS = 8
PRICE_RESPONSE_PROBABILITY = 0.40
PRICE_ELASTICITY_RANGE = (0.05, 0.10)
PEAK_TARIFF_MULTIPLIER = 1.6


@dataclass
class Offer:
    household_id: str
    kw: float
    score: float
    device_kind: str


@dataclass
class VidyutController:
    forecaster: Forecaster
    name: str = "vidyut"
    state: ControllerState = field(default_factory=ControllerState)
    outbox: Outbox = field(default_factory=Outbox)
    last_reconfig_tick: int = -RECONFIG_INTERVAL_TICKS
    shifted_runs: set[int] = field(default_factory=set)
    last_price_signal_tick: dict[str, int] = field(default_factory=dict)
    last_curtailed_tick: dict[str, int] = field(default_factory=dict)
    last_forecast: dict | None = None

    def act(self, world: World, tick: int, result: PowerFlowResult) -> list[TickEvent]:
        forecast = self.forecaster.predict(tick, max(FORECAST_HORIZON, SHIFT_HORIZON))
        self._record_headline_forecast(world, forecast)

        self._tier1_shift(world, tick, forecast)
        self._tier1_reconfigure(world, tick, result)
        self._tier2_preemptive(world, tick, forecast)
        if result.converged:
            self._tier3_last_resort(world, tick, result)

        return self.state.drain()

    def _record_headline_forecast(self, world: World, forecast: np.ndarray) -> None:
        if forecast.size == 0:
            self.last_forecast = None
            return

        safe_limits = np.array([world.safe_limit_kw(dt_id) for dt_id in world.dt_ids])
        headroom = forecast[:, :FORECAST_HORIZON].max(axis=1) / np.maximum(safe_limits, 1e-6)
        row = int(np.argmax(headroom))
        dt_id = world.dt_ids[row]

        self.last_forecast = {
            "dt_id": dt_id,
            "horizon_kw": [round(float(v), 1) for v in forecast[row, :FORECAST_HORIZON]],
            "safe_limit_kw": round(float(safe_limits[row]), 1),
            "rating_kw": round(world.rating_kw(dt_id), 1),
        }

    # Tier 1 - steady state, no comfort impact

    def _tier1_shift(self, world: World, tick: int, forecast: np.ndarray) -> None:
        shifted_kw = 0.0
        shifted_count = 0
        targets: set[str] = set()

        for idx, run in enumerate(world.demand.deferrable):
            if idx in self.shifted_runs or not run.controllable:
                continue
            if run.start <= tick or run.start > tick + SHIFT_HORIZON:
                continue

            dt_id = world.households[run.hh_id].dt_id
            row = world.dt_row[dt_id]
            safe_limit = world.safe_limit_kw(dt_id)
            horizon_offset = run.start - tick - 1
            if horizon_offset >= forecast.shape[1]:
                continue
            if forecast[row, horizon_offset] <= safe_limit:
                continue

            latest_start = run.natural_start + run.window_ticks
            new_start = self._first_clear_tick(
                forecast, row, tick, run.start + 1, latest_start, safe_limit
            )
            if new_start is None:
                continue

            run.start = min(new_start, N_TICKS - run.duration_ticks)
            self.shifted_runs.add(idx)
            shifted_kw += run.rated_kw
            shifted_count += 1
            targets.add(dt_id)

        if shifted_count:
            self.state.emit(
                tier=1,
                action="device_shift",
                target=",".join(sorted(targets)[:3]),
                kw=shifted_kw,
                households=shifted_count,
                reason_code=ReasonCode.STEADY_STATE_SHIFT,
                detail=(
                    f"{shifted_count} deferrable loads rescheduled within their windows, "
                    f"{shifted_kw:.0f} kW moved off the forecast peak"
                ),
            )

    def _first_clear_tick(
        self,
        forecast: np.ndarray,
        row: int,
        tick: int,
        earliest: int,
        latest: int,
        safe_limit: float,
    ) -> int | None:
        for candidate in range(earliest, min(latest, N_TICKS - 1) + 1):
            offset = candidate - tick - 1
            if offset < 0 or offset >= forecast.shape[1]:
                return candidate
            if forecast[row, offset] <= safe_limit:
                return candidate
        return None

    def _tier1_reconfigure(self, world: World, tick: int, result: PowerFlowResult) -> None:
        if tick - self.last_reconfig_tick < RECONFIG_INTERVAL_TICKS:
            return
        if not result.converged:
            return

        loadings = list(result.feeder_loading_pct.values())
        spread = max(loadings) - min(loadings)
        if spread < RECONFIG_TRIGGER_SPREAD_PCT and max(loadings) < RECONFIG_TRIGGER_LOADING_PCT:
            return

        self.last_reconfig_tick = tick
        candidate = evaluate_reconfiguration(world, result)
        if candidate is None:
            return

        before = {f: round(v) for f, v in result.feeder_loading_pct.items()}
        apply_reconfiguration(world, candidate)
        after = {f: round(v) for f, v in candidate.result.feeder_loading_pct.items()}

        self.state.emit(
            tier=1,
            action="reconfigure",
            target=candidate.pair.tie_switch_id,
            kw=result.losses_kw - candidate.result.losses_kw,
            households=0,
            reason_code=ReasonCode.RECONFIGURATION,
            detail=(
                f"closed {candidate.pair.tie_switch_id}, opened switch "
                f"{candidate.pair.open_switch}; feeder loading {before} to {after}"
            ),
        )

    # Tier 2 - pre-emptive, device level then meter load limit

    def _tier2_preemptive(self, world: World, tick: int, forecast: np.ndarray) -> None:
        for dt_id in world.dt_ids:
            if not world.dt_energized[dt_id]:
                continue

            row = world.dt_row[dt_id]
            horizon = forecast[row, :FORECAST_HORIZON]
            if horizon.size == 0:
                continue

            predicted_kw = float(horizon.max())
            safe_limit = world.safe_limit_kw(dt_id)
            need_kw = predicted_kw - safe_limit
            if need_kw <= 0.0:
                continue

            price_kw, n_priced = self._broadcast_price_signal(world, tick, dt_id, need_kw)
            if n_priced:
                self.state.emit(
                    tier=0,
                    action="price_signal",
                    target=dt_id,
                    kw=price_kw,
                    households=n_priced,
                    reason_code=ReasonCode.PRICE_SIGNAL_PEAK,
                    detail=(
                        f"{dt_id} peak tariff {PEAK_TARIFF_MULTIPLIER:.1f}x broadcast to "
                        f"{n_priced} households without controllable devices; "
                        f"{price_kw:.0f} kW expected voluntary response"
                    ),
                )

            need_kw -= price_kw
            if need_kw <= 0.0:
                continue

            cleared_kw, n_devices = self._clear_with_devices(world, tick, dt_id, need_kw)
            remaining = need_kw - cleared_kw

            if n_devices:
                self.state.emit(
                    tier=2,
                    action="device_curtail",
                    target=dt_id,
                    kw=cleared_kw,
                    households=n_devices,
                    reason_code=ReasonCode.PRE_EMPTIVE_THERMAL,
                    detail=(
                        f"{dt_id} forecast {predicted_kw:.0f} kW against safe limit "
                        f"{safe_limit:.0f} kW; {n_devices} connected devices curtailed"
                    ),
                )

            if remaining > 0.0:
                limited_kw, n_limited = self._clear_with_load_limit(
                    world, tick, dt_id, remaining
                )
                if n_limited:
                    self.state.emit(
                        tier=2,
                        action="meter_load_limit",
                        target=dt_id,
                        kw=limited_kw,
                        households=n_limited,
                        reason_code=ReasonCode.ESCALATION_LOAD_LIMIT,
                        detail=(
                            f"{dt_id} short {remaining:.0f} kW after device curtailment; "
                            f"temporary load ceiling on {n_limited} standard-tier households"
                        ),
                    )

    def _broadcast_price_signal(
        self, world: World, tick: int, dt_id: str, need_kw: float
    ) -> tuple[float, int]:
        last = self.last_price_signal_tick.get(dt_id)
        if last is not None and tick - last < PRICE_SIGNAL_COOLDOWN_TICKS:
            return 0.0, 0

        rng = world.rngs["controller"]
        recipients = [
            hh_id
            for hh_id in world.ctx.dts[dt_id].households
            if not world.households[hh_id].addressable
            and world.households[hh_id].tier != "critical"
        ]
        if not recipients:
            return 0.0, 0

        self.last_price_signal_tick[dt_id] = tick
        expected_kw = 0.0
        responders = 0
        reference_tick = min(tick + 1, N_TICKS - 1)

        for hh_id in recipients:
            if rng.random() > PRICE_RESPONSE_PROBABILITY:
                continue
            elasticity = rng.uniform(*PRICE_ELASTICITY_RANGE)
            baseline_kw = float(world.demand.base_kw[world.demand.row_of[hh_id], reference_tick])
            reduction = elasticity * baseline_kw
            if reduction <= 0.0:
                continue

            world.actuation.issue(
                ActuationCommand(
                    household_id=hh_id,
                    dt_id=dt_id,
                    level="price_signal",
                    kw_reduction=reduction,
                    issued_tick=tick + 1,
                    expires_tick=tick + 1 + PRICE_SIGNAL_TICKS,
                    reason_code=ReasonCode.PRICE_SIGNAL_PEAK,
                )
            )
            expected_kw += reduction
            responders += 1

        self.outbox.add(
            Notification(
                tick=tick,
                clock=clock_of(tick),
                channel="tod_price_broadcast",
                event_type="price_signal",
                dt_id=dt_id,
                feeder_id=world.ctx.feeder_of_dt[dt_id],
                households=len(recipients),
                reason_code=ReasonCode.PRICE_SIGNAL_PEAK,
                message=(
                    f"Peak tariff of {PEAK_TARIFF_MULTIPLIER:.1f}x applies for the next "
                    f"{PRICE_SIGNAL_TICKS * TICK_MINUTES} minutes in your area. Shifting heavy "
                    f"appliance use past this window will lower your bill."
                ),
                tariff_multiplier=PEAK_TARIFF_MULTIPLIER,
                expected_reduction_kw=round(expected_kw, 2),
                window_minutes=PRICE_SIGNAL_TICKS * TICK_MINUTES,
            )
        )
        return expected_kw, responders

    def _clear_with_devices(
        self, world: World, tick: int, dt_id: str, need_kw: float
    ) -> tuple[float, int]:
        offers = self._collect_offers(world, tick, dt_id, respect_cooldown=True)
        if sum(o.kw for o in offers) < need_kw:
            offers = self._collect_offers(world, tick, dt_id, respect_cooldown=False)
        offers.sort(key=lambda o: o.score)

        cleared = 0.0
        selected = 0
        for offer in offers:
            if cleared >= need_kw:
                break
            self.last_curtailed_tick[offer.household_id] = tick
            world.actuation.issue(
                ActuationCommand(
                    household_id=offer.household_id,
                    dt_id=dt_id,
                    level="device",
                    kw_reduction=offer.kw,
                    issued_tick=tick + 1,
                    expires_tick=tick + 1 + DEVICE_CURTAIL_TICKS,
                    reason_code=ReasonCode.PRE_EMPTIVE_THERMAL,
                    device_kind=offer.device_kind,
                )
            )
            world.ledger.charge(
                tick=tick,
                household_id=offer.household_id,
                dt_id=dt_id,
                level="device",
                kw=offer.kw,
                minutes=DEVICE_CURTAIL_TICKS * TICK_MINUTES,
                reason_code=ReasonCode.PRE_EMPTIVE_THERMAL,
            )
            cleared += offer.kw
            selected += 1
        return cleared, selected

    def _collect_offers(
        self, world: World, tick: int, dt_id: str, respect_cooldown: bool
    ) -> list[Offer]:
        offers: list[Offer] = []
        stress = world.demand.thermal_stress[min(tick + 1, N_TICKS - 1)]
        active_commands = {c.household_id for c in world.actuation.active(tick + 1)}

        for hh_id in world.ctx.dts[dt_id].households:
            household = world.households[hh_id]
            if household.tier == "critical" or hh_id in active_commands:
                continue

            last = self.last_curtailed_tick.get(hh_id)
            if respect_cooldown and last is not None and tick - last < CURTAIL_COOLDOWN_TICKS:
                continue

            normalised_debt = world.ledger.normalised_debt(hh_id)
            for device in household.devices:
                if not device.controllable:
                    continue

                kw = device.rated_kw * stress if device.kind == "ac" else device.rated_kw
                if device.kind != "ac" and not self._run_active(world, hh_id, device.kind, tick + 1):
                    continue
                if kw <= 0.01:
                    continue

                cost_per_kw = device.comfort_cost_per_min * TICK_MINUTES / kw
                offers.append(
                    Offer(
                        household_id=hh_id,
                        kw=kw,
                        score=cost_per_kw * (1.0 + DEBT_WEIGHT * normalised_debt),
                        device_kind=device.kind,
                    )
                )
        return offers

    def _run_active(self, world: World, hh_id: str, kind: str, tick: int) -> bool:
        return any(
            run.hh_id == hh_id and run.kind == kind and run.draws_at(tick)
            for run in world.demand.deferrable
        )

    def _clear_with_load_limit(
        self, world: World, tick: int, dt_id: str, need_kw: float
    ) -> tuple[float, int]:
        eligible = [
            hh_id
            for hh_id in world.ctx.dts[dt_id].households
            if world.households[hh_id].tier == "standard"
            and world.households[hh_id].ami
            and world.households[hh_id].meter_load_limit_supported
        ]
        eligible.sort(key=world.ledger.debt_of)

        row = world.dt_row[dt_id]
        per_household_kw = LOAD_LIMIT_REDUCTION_FRACTION * max(
            world.demand.base_kw[world.demand.row_of[eligible[0]], tick] if eligible else 0.0, 0.4
        )

        cleared = 0.0
        selected = 0
        for hh_id in eligible:
            if cleared >= need_kw:
                break
            world.actuation.issue(
                ActuationCommand(
                    household_id=hh_id,
                    dt_id=dt_id,
                    level="load_limit",
                    kw_reduction=per_household_kw,
                    issued_tick=tick + 1,
                    expires_tick=tick + 1 + LOAD_LIMIT_TICKS,
                    reason_code=ReasonCode.ESCALATION_LOAD_LIMIT,
                )
            )
            world.ledger.charge(
                tick=tick,
                household_id=hh_id,
                dt_id=dt_id,
                level="load_limit",
                kw=per_household_kw,
                minutes=LOAD_LIMIT_TICKS * TICK_MINUTES,
                reason_code=ReasonCode.ESCALATION_LOAD_LIMIT,
            )
            cleared += per_household_kw
            selected += 1
        return cleared, selected

    # Tier 3 - last resort, rotational and standard tier only

    def _tier3_last_resort(self, world: World, tick: int, result: PowerFlowResult) -> None:
        for dt_id in world.dt_ids:
            if not world.dt_energized[dt_id]:
                continue

            loading = float(result.trafo_loading_pct[world.ctx.dt_trafo_idx[dt_id]])
            if loading <= EMERGENCY_LOADING_PCT:
                continue

            rating_kw = world.rating_kw(dt_id)
            need_kw = (loading - EMERGENCY_LOADING_PCT) / 100.0 * rating_kw

            already = world.actuation.households_disconnected(tick + 1)
            eligible = [
                hh_id
                for hh_id in world.ctx.dts[dt_id].households
                if world.households[hh_id].tier == "standard" and hh_id not in already
            ]
            eligible.sort(key=world.ledger.debt_of)

            household_kw = world.demand.base_kw[:, min(tick + 1, N_TICKS - 1)]
            cleared = 0.0
            selected = 0
            for hh_id in eligible:
                if cleared >= need_kw:
                    break
                kw = float(household_kw[world.demand.row_of[hh_id]])
                world.actuation.issue(
                    ActuationCommand(
                        household_id=hh_id,
                        dt_id=dt_id,
                        level="disconnect",
                        kw_reduction=kw,
                        issued_tick=tick + 1,
                        expires_tick=tick + 1 + DISCONNECT_TICKS,
                        reason_code=ReasonCode.LAST_RESORT_ROTATION,
                    )
                )
                world.ledger.charge(
                    tick=tick,
                    household_id=hh_id,
                    dt_id=dt_id,
                    level="disconnect",
                    kw=kw,
                    minutes=DISCONNECT_TICKS * TICK_MINUTES,
                    reason_code=ReasonCode.LAST_RESORT_ROTATION,
                )
                cleared += kw
                selected += 1

            if selected:
                self.state.emit(
                    tier=3,
                    action="rotational_disconnect",
                    target=dt_id,
                    kw=cleared,
                    households=selected,
                    reason_code=ReasonCode.LAST_RESORT_ROTATION,
                    detail=(
                        f"{dt_id} measured {loading:.0f}% after flexibility exhausted; "
                        f"{selected} standard-tier households rotated off for "
                        f"{DISCONNECT_TICKS * TICK_MINUTES} minutes, lowest accumulated debt first"
                    ),
                )
