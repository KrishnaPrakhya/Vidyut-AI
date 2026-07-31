from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Feeder(Base):
    __tablename__ = "feeder"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    substation: Mapped[str] = mapped_column(String(32), default="SUB")
    nominal_kv: Mapped[float] = mapped_column(Numeric(8, 3), default=11.0)
    trunk_conductor: Mapped[str | None] = mapped_column(String(64), nullable=True)


class DistributionTransformerRow(Base):
    __tablename__ = "distribution_transformer"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    feeder_id: Mapped[str] = mapped_column(ForeignKey("feeder.id"), index=True)
    rating_kva: Mapped[float] = mapped_column(Numeric(10, 2))


class Household(Base):
    __tablename__ = "household"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    dt_id: Mapped[str] = mapped_column(ForeignKey("distribution_transformer.id"), index=True)
    tier: Mapped[str] = mapped_column(String(16), index=True)
    ami: Mapped[bool] = mapped_column(Boolean, default=False)
    meter_load_limit_supported: Mapped[bool] = mapped_column(Boolean, default=False)
    has_connected_device: Mapped[bool] = mapped_column(Boolean, default=False)
    addressable: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    consent_dr: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    devices: Mapped[list[Device]] = relationship(back_populates="household")


class Device(Base):
    __tablename__ = "device"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    household_id: Mapped[str] = mapped_column(ForeignKey("household.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    rated_kw: Mapped[float] = mapped_column(Numeric(8, 3))
    controllable: Mapped[bool] = mapped_column(Boolean, default=False)
    deferrable_window_min: Mapped[int] = mapped_column(Integer, default=0)
    comfort_cost_per_min: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)

    household: Mapped[Household] = relationship(back_populates="devices")


class Run(Base):
    __tablename__ = "run"

    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    scenario: Mapped[str] = mapped_column(String(32), index=True)
    seed: Mapped[int] = mapped_column(Integer, index=True)
    ticks: Mapped[int] = mapped_column(Integer)
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    error: Mapped[str | None] = mapped_column(Text)
    sim_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunInjection(Base):
    __tablename__ = "run_injection"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(24))
    magnitude: Mapped[float] = mapped_column(Numeric(8, 3))
    from_tick: Mapped[int] = mapped_column(Integer)
    dt_id: Mapped[str | None] = mapped_column(String(32))


class RunArmTotal(Base):
    __tablename__ = "run_arm_total"
    __table_args__ = (UniqueConstraint("run_id", "arm"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id", ondelete="CASCADE"), index=True)
    arm: Mapped[str] = mapped_column(String(16))

    served_kwh: Mapped[float] = mapped_column(Numeric(14, 3))
    unserved_kwh: Mapped[float] = mapped_column(Numeric(14, 3))
    demanded_kwh: Mapped[float] = mapped_column(Numeric(14, 3))
    flexibility_kwh: Mapped[float] = mapped_column(Numeric(14, 3))
    energy_balance_error_kwh: Mapped[float] = mapped_column(Numeric(14, 6))
    unserved_cost_rs: Mapped[float] = mapped_column(Numeric(14, 2))
    peak_kva: Mapped[float] = mapped_column(Numeric(12, 2))
    max_trafo_loading_pct: Mapped[float] = mapped_column(Numeric(8, 2))
    mean_spread_pct: Mapped[float] = mapped_column(Numeric(8, 2))
    max_spread_pct: Mapped[float] = mapped_column(Numeric(8, 2))
    total_losses_kwh: Mapped[float] = mapped_column(Numeric(12, 3))
    losses_pct_of_delivered: Mapped[float] = mapped_column(Numeric(8, 4))
    homes_dark_minutes: Mapped[float] = mapped_column(Numeric(14, 2))
    peak_homes_dark: Mapped[int] = mapped_column(Integer)
    critical_uptime_pct: Mapped[float] = mapped_column(Numeric(9, 5))
    gini: Mapped[float] = mapped_column(Numeric(8, 5))
    gini_affected: Mapped[float] = mapped_column(Numeric(8, 5))
    max_household_burden_min: Mapped[float] = mapped_column(Numeric(12, 2))
    households_curtailed: Mapped[int] = mapped_column(Integer)
    nonconverged_ticks: Mapped[int] = mapped_column(Integer)
    addressable_share_of_load: Mapped[float] = mapped_column(Numeric(8, 5))
    minutes_by_level: Mapped[dict] = mapped_column(JSONB, default=dict)
    events_by_tier: Mapped[dict] = mapped_column(JSONB, default=dict)


class TickMetric(Base):
    __tablename__ = "tick_metric"
    __table_args__ = (Index("ix_tick_metric_run_arm_tick", "run_id", "arm", "tick"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id", ondelete="CASCADE"))
    arm: Mapped[str] = mapped_column(String(16))
    tick: Mapped[int] = mapped_column(Integer)
    converged: Mapped[bool] = mapped_column(Boolean)
    peak_kva: Mapped[float] = mapped_column(Numeric(12, 2))
    spread_pct: Mapped[float] = mapped_column(Numeric(8, 2))
    losses_kw: Mapped[float] = mapped_column(Numeric(10, 3))
    homes_dark: Mapped[int] = mapped_column(Integer)
    critical_uptime_pct: Mapped[float] = mapped_column(Numeric(9, 5))
    unserved_kwh: Mapped[float] = mapped_column(Numeric(12, 3))
    gini: Mapped[float] = mapped_column(Numeric(8, 5))
    max_trafo_loading_pct: Mapped[float] = mapped_column(Numeric(8, 2))


class DtTickReading(Base):
    __tablename__ = "dt_tick_reading"
    __table_args__ = (Index("ix_dt_tick_run_arm_tick", "run_id", "arm", "tick"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id", ondelete="CASCADE"))
    arm: Mapped[str] = mapped_column(String(16))
    tick: Mapped[int] = mapped_column(Integer)
    dt_id: Mapped[str] = mapped_column(String(32))
    loading_pct: Mapped[float] = mapped_column(Numeric(8, 2))
    energized: Mapped[bool] = mapped_column(Boolean)
    households_dark: Mapped[int] = mapped_column(Integer)


class FeederTickReading(Base):
    __tablename__ = "feeder_tick_reading"
    __table_args__ = (Index("ix_feeder_tick_run_arm_tick", "run_id", "arm", "tick"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id", ondelete="CASCADE"))
    arm: Mapped[str] = mapped_column(String(16))
    tick: Mapped[int] = mapped_column(Integer)
    feeder_id: Mapped[str] = mapped_column(String(16))
    loading_pct: Mapped[float] = mapped_column(Numeric(8, 2))
    losses_kw: Mapped[float] = mapped_column(Numeric(10, 3))


class ControlAction(Base):
    __tablename__ = "control_action"
    __table_args__ = (
        Index("ix_control_action_run_arm_tick", "run_id", "arm", "tick"),
        Index("ix_control_action_reason", "reason_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id", ondelete="CASCADE"))
    arm: Mapped[str] = mapped_column(String(16))
    tick: Mapped[int] = mapped_column(Integer)
    clock: Mapped[str] = mapped_column(String(5))
    tier: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(32))
    target: Mapped[str] = mapped_column(String(48), index=True)
    kw: Mapped[float] = mapped_column(Numeric(12, 3))
    households: Mapped[int] = mapped_column(Integer)
    reason_code: Mapped[str] = mapped_column(String(48))
    detail: Mapped[str | None] = mapped_column(Text)
    forecast_kw: Mapped[float | None] = mapped_column(Numeric(12, 3))
    safe_limit_kw: Mapped[float | None] = mapped_column(Numeric(12, 3))

    impacts: Mapped[list[HouseholdImpact]] = relationship(back_populates="action")


class HouseholdImpact(Base):
    __tablename__ = "household_impact"
    __table_args__ = (
        Index("ix_household_impact_household_run", "household_id", "run_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    action_id: Mapped[int | None] = mapped_column(
        ForeignKey("control_action.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id", ondelete="CASCADE"))
    arm: Mapped[str] = mapped_column(String(16))
    tick: Mapped[int] = mapped_column(Integer)
    household_id: Mapped[str] = mapped_column(String(48))
    dt_id: Mapped[str] = mapped_column(String(32), index=True)
    level: Mapped[str] = mapped_column(String(24), index=True)
    device_kind: Mapped[str | None] = mapped_column(String(24))
    kw_reduction: Mapped[float] = mapped_column(Numeric(10, 3))
    minutes: Mapped[float] = mapped_column(Numeric(10, 2))
    debt_weight: Mapped[float] = mapped_column(Numeric(6, 2))
    debt_charged: Mapped[float] = mapped_column(Numeric(12, 3))
    standing_percentile: Mapped[float | None] = mapped_column(Numeric(6, 3))
    reason_code: Mapped[str] = mapped_column(String(48))

    action: Mapped[ControlAction | None] = relationship(back_populates="impacts")


class FairnessLedger(Base):
    __tablename__ = "fairness_ledger"

    household_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    dt_id: Mapped[str] = mapped_column(String(32), index=True)
    cumulative_debt_min: Mapped[float] = mapped_column(Numeric(14, 3), default=0.0, index=True)
    events_count: Mapped[int] = mapped_column(Integer, default=0)
    minutes_by_level: Mapped[dict] = mapped_column(JSONB, default=dict)
    first_curtailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_curtailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FairnessLedgerHistory(Base):
    __tablename__ = "fairness_ledger_history"
    __table_args__ = (Index("ix_ledger_history_household", "household_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    household_id: Mapped[str] = mapped_column(String(48))
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id", ondelete="CASCADE"))
    debt_before: Mapped[float] = mapped_column(Numeric(14, 3))
    debt_delta: Mapped[float] = mapped_column(Numeric(14, 3))
    debt_after: Mapped[float] = mapped_column(Numeric(14, 3))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id", ondelete="CASCADE"), index=True)
    tick: Mapped[int] = mapped_column(Integer)
    clock: Mapped[str] = mapped_column(String(5))
    channel: Mapped[str] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(32))
    dt_id: Mapped[str] = mapped_column(String(32), index=True)
    feeder_id: Mapped[str] = mapped_column(String(16))
    households: Mapped[int] = mapped_column(Integer)
    reason_code: Mapped[str] = mapped_column(String(48))
    message: Mapped[str] = mapped_column(Text)
    tariff_multiplier: Mapped[float | None] = mapped_column(Numeric(6, 3))
    expected_reduction_kw: Mapped[float | None] = mapped_column(Numeric(10, 3))
    window_minutes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationDelivery(Base):
    __tablename__ = "notification_delivery"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notification.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="n8n")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(128))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class TopologyChange(Base):
    __tablename__ = "topology_change"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.run_id", ondelete="CASCADE"), index=True)
    arm: Mapped[str] = mapped_column(String(16))
    tick: Mapped[int] = mapped_column(Integer)
    tie_switch_closed: Mapped[str] = mapped_column(String(32))
    switch_opened: Mapped[int] = mapped_column(Integer)
    losses_kw_before: Mapped[float | None] = mapped_column(Numeric(10, 3))
    losses_kw_after: Mapped[float | None] = mapped_column(Numeric(10, 3))
    detail: Mapped[str | None] = mapped_column(Text)
