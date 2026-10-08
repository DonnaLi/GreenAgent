from __future__ import annotations

import os
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

load_dotenv()

# SQLite by default so the app runs with zero setup.
# Set DATABASE_URL in .env to use the PostgreSQL from docker-compose.
DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./green_agent.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origin: Mapped[str] = mapped_column(String(120))
    destination: Mapped[str] = mapped_column(String(120))
    weight_kg: Mapped[float] = mapped_column(Float)
    deadline: Mapped[datetime] = mapped_column(DateTime)
    w_carbon: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    recommended_carrier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale_source: Mapped[str] = mapped_column(String(20), default="template")
    co2e_saved_kg: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    bids: Mapped[list[Bid]] = relationship(
        back_populates="shipment",
        cascade="all, delete-orphan",
        # Ranked bids first, excluded (unranked) bids last.
        order_by=lambda: (Bid.rank.is_(None), Bid.rank),
    )


class Bid(Base):
    __tablename__ = "bids"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"))
    carrier_id: Mapped[str] = mapped_column(String(50))
    carrier_name: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(50))
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    eta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    co2e_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    norm_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    norm_co2e: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    excluded_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    shipment: Mapped[Shipment] = relationship(back_populates="bids")


def init_db() -> None:
    Base.metadata.create_all(engine)
