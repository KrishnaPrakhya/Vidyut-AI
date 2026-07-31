from __future__ import annotations

from alembic import op

revision = "0002_notification_delivery_unique"
down_revision = "0001_current_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM notification_delivery a USING notification_delivery b "
        "WHERE a.notification_id = b.notification_id AND a.id < b.id"
    )
    op.create_unique_constraint(
        "uq_notification_delivery_notification_id",
        "notification_delivery",
        ["notification_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_notification_delivery_notification_id",
        "notification_delivery",
        type_="unique",
    )
