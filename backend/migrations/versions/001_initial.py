"""Initial schema — all AEGIS tables.

Revision ID: 001_initial
Revises: None
Create Date: 2026-07-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "positions",
        sa.Column("symbol", sa.String, primary_key=True),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("average_price", sa.Float, nullable=False),
    )

    op.create_table(
        "paper_orders",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String, nullable=False),
        sa.Column("side", sa.String, nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("reference_price", sa.Float, nullable=False),
        sa.Column("notional", sa.Float, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
    )

    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String, nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("collected_at", sa.String, nullable=False),
    )
    op.create_index("idx_market_snapshots_symbol_collected_at", "market_snapshots", ["symbol", "collected_at"])

    op.create_table(
        "ohlcv_candles",
        sa.Column("symbol", sa.String, nullable=False),
        sa.Column("interval", sa.String, nullable=False),
        sa.Column("open_time", sa.Integer, nullable=False),
        sa.Column("close_time", sa.Integer, nullable=False),
        sa.Column("open", sa.Float, nullable=False),
        sa.Column("high", sa.Float, nullable=False),
        sa.Column("low", sa.Float, nullable=False),
        sa.Column("close", sa.Float, nullable=False),
        sa.Column("volume", sa.Float, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.PrimaryKeyConstraint("symbol", "interval", "open_time"),
    )

    op.create_table(
        "backtests",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("strategy", sa.String, nullable=False),
        sa.Column("symbol", sa.String, nullable=False),
        sa.Column("interval", sa.String, nullable=False),
        sa.Column("parameters_json", sa.Text, nullable=False),
        sa.Column("metrics_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
    )

    op.create_table(
        "decision_journal",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String, nullable=False),
        sa.Column("interval", sa.String, nullable=False),
        sa.Column("decision_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
    )

    op.create_table(
        "system_controls",
        sa.Column("name", sa.String, primary_key=True),
        sa.Column("value", sa.String, nullable=False),
        sa.Column("updated_at", sa.String, nullable=False),
    )

    op.create_table(
        "system_alerts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("severity", sa.String, nullable=False),
        sa.Column("message", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
    )

    op.create_table(
        "fear_greed",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("value", sa.Integer, nullable=False),
        sa.Column("classification", sa.String, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("collected_at", sa.String, nullable=False),
    )

    op.create_table(
        "funding_rates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String, nullable=False),
        sa.Column("mark_price", sa.Float, nullable=False),
        sa.Column("index_price", sa.Float, nullable=False),
        sa.Column("funding_rate", sa.Float, nullable=False),
        sa.Column("next_funding_time", sa.Integer, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("collected_at", sa.String, nullable=False),
    )
    op.create_index("idx_funding_rates_symbol_collected_at", "funding_rates", ["symbol", "collected_at"])

    op.create_table(
        "open_interest",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String, nullable=False),
        sa.Column("open_interest", sa.Float, nullable=False),
        sa.Column("open_interest_usd", sa.Float, nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("collected_at", sa.String, nullable=False),
    )
    op.create_index("idx_open_interest_symbol_collected_at", "open_interest", ["symbol", "collected_at"])

    op.create_table(
        "memory_episodes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String, nullable=False),
        sa.Column("strategy", sa.String, nullable=False),
        sa.Column("features_json", sa.Text, nullable=False),
        sa.Column("result_json", sa.Text, nullable=True),
        sa.Column("fingerprint", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
    )
    op.create_index("idx_memory_fingerprint", "memory_episodes", ["fingerprint"])


def downgrade() -> None:
    op.drop_table("memory_episodes")
    op.drop_table("open_interest")
    op.drop_table("funding_rates")
    op.drop_table("fear_greed")
    op.drop_table("system_alerts")
    op.drop_table("system_controls")
    op.drop_table("decision_journal")
    op.drop_table("backtests")
    op.drop_table("ohlcv_candles")
    op.drop_table("market_snapshots")
    op.drop_table("paper_orders")
    op.drop_table("positions")
