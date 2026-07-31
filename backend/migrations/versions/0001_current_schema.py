from __future__ import annotations

from alembic import op
from sqlalchemy import Boolean, Column, Numeric, inspect

from services.persistence.models import Base

revision = "0001_current_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    inspector = inspect(bind)
    arm_columns = {
        column["name"] for column in inspector.get_columns("run_arm_total")
    }
    additions = {
        "demanded_kwh": Numeric(14, 3),
        "flexibility_kwh": Numeric(14, 3),
        "energy_balance_error_kwh": Numeric(14, 6),
    }
    for name, data_type in additions.items():
        if name not in arm_columns:
            op.add_column(
                "run_arm_total",
                Column(name, data_type, nullable=False, server_default="0"),
            )
    tick_columns = {
        column["name"] for column in inspect(bind).get_columns("tick_metric")
    }
    if "converged" not in tick_columns:
        op.add_column(
            "tick_metric",
            Column("converged", Boolean(), nullable=False, server_default="true"),
        )


def downgrade() -> None:
    pass
