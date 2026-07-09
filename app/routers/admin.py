"""Administrative reporting and export endpoints."""
from datetime import datetime, time, timedelta, timezone
from typing import cast

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import cache
from ..auth import require_admin
from ..database import get_db
from ..errors import AppError
from ..models import Booking, Room, User
from ..services.export import generate_export

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/usage-report")
def usage_report(
    frm: str = Query(..., alias="from"),
    to: str = Query(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    cached = cache.get_report(cast(int, admin.org_id), frm, to)
    if cached is not None:
        return cached

    try:
        from_date = datetime.strptime(frm, "%Y-%m-%d").date()
        to_date = datetime.strptime(to, "%Y-%m-%d").date()
    except ValueError:
        raise AppError(400, "INVALID_BOOKING_WINDOW", "Invalid date range")

    parsed_from_date = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
    parsed_to_date = datetime.combine(to_date, time.min, tzinfo=timezone.utc)

    rooms = db.query(Room).filter(Room.org_id == admin.org_id).order_by(Room.id.asc()).all()
    room_rows = []
    for room in rooms:
        bookings = (
            db.query(Booking)
            .filter(
                Booking.room_id == room.id,
                Booking.status == "confirmed",
                Booking.start_time >= parsed_from_date,
                Booking.start_time < (parsed_to_date + timedelta(days=1)),
            )
            .all()
        )
        room_rows.append(
            {
                "room_id": room.id,
                "room_name": room.name,
                "confirmed_bookings": len(bookings),
                "revenue_cents": sum(b.price_cents for b in bookings),
            }
        )

    result = {"from": frm, "to": to, "rooms": room_rows}
    cache.set_report(cast(int, admin.org_id), frm, to, result)
    return result


@router.get("/export")
def export(
    room_id: int | None = Query(None),
    include_all: bool = Query(False),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if room_id is not None:
        room = db.query(Room).filter(Room.id == room_id).first()
        if room is None or room.org_id != admin.org_id:
            raise AppError(404, "ROOM_NOT_FOUND", "Room not found")

    csv_body = generate_export(db, cast(int, admin.org_id), cast(int, admin.id), room_id, include_all)
    return Response(content=csv_body, media_type="text/csv")
