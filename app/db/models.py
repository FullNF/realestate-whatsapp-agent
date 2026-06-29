"""
Data model, deliberately shaped around how this business actually sells:

- `AreaInventory` is area/BHK/furnishing-tier rows (NOT individual flats).
  The agent always reads from this table to quote availability/price —
  it never invents a number from the LLM's own "knowledge".
- `Lead` carries the qualification fields the agent collects (name, area,
  BHK, furnishing, budget, timeline) plus the out-of-area attempt counter
  and status, so the redirect-then-close logic is deterministic and
  survives across messages/days.
- `LeadControl` is the exception list — pause the agent for a specific
  phone number without touching code.
- `Message` is the conversation log, also used for idempotency (a given
  WhatsApp message id is only ever processed once, even if Meta retries
  the webhook delivery).
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    area_requested: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bhk_requested: Mapped[str | None] = mapped_column(String(40), nullable=True)
    furnishing_pref: Mapped[str | None] = mapped_column(String(40), nullable=True)
    budget_mentioned: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timeline_mentioned: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # active | site_visit_requested | closed_out_of_area | closed_manual
    status: Mapped[str] = mapped_column(String(32), default="active")
    out_of_area_attempts: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    messages: Mapped[list["Message"]] = relationship(back_populates="lead", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    direction: Mapped[str] = mapped_column(String(8))  # "in" | "out"
    wa_message_id: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True, index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    lead: Mapped["Lead"] = relationship(back_populates="messages")


class AreaInventory(Base):
    __tablename__ = "area_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sector: Mapped[str] = mapped_column(String(120), index=True)
    project_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bhk_type: Mapped[str] = mapped_column(String(40))
    available_label: Mapped[str | None] = mapped_column(String(60), nullable=True)  # e.g. "5-6 units"
    price_raw: Mapped[str | None] = mapped_column(String(60), nullable=True)
    price_semi_furnished: Mapped[str | None] = mapped_column(String(60), nullable=True)
    price_fully_furnished: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LeadControl(Base):
    """The exception list: pause the AI agent for a specific phone number."""

    __tablename__ = "lead_controls"

    phone: Mapped[str] = mapped_column(String(32), primary_key=True)
    agent_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
