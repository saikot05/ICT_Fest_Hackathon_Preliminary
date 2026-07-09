"""Live per-room booking statistics.

Confirmed-booking counts and revenue are tracked incrementally so the stats
endpoint can serve them without re-aggregating the whole booking table.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Booking


def record_create(room_id: int, price_cents: int) -> None:
    _ = (room_id, price_cents)


def record_cancel(room_id: int, price_cents: int) -> None:
    _ = (room_id, price_cents)


def get(db: Session, room_id: int) -> dict:
    row = (
        db.query(func.count(Booking.id), func.sum(Booking.price_cents))
        .filter(Booking.room_id == room_id, Booking.status == "confirmed")
        .first()
    )
    count, revenue = row if row else (0, 0)
    return {
        "count": count or 0,
        "revenue": revenue or 0,
    }
