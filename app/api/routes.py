"""Rutas HTTP: capa delgada que delega en los casos de uso."""

from datetime import datetime

from fastapi import APIRouter, Query, Request, status

from app.api.schemas import (
    CancellationResponse,
    CreateReservationRequest,
    ReservationResponse,
)

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    return {
        "status": "ok",
        "seed_warnings": request.app.state.seed_report.warnings,
    }


@router.post(
    "/reservations",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reservation(request: Request, body: CreateReservationRequest):
    reservation = request.app.state.create_reservation.execute(
        user_id=body.user_id,
        service_id=body.service_id,
        start=body.start,
    )
    return ReservationResponse.from_domain(reservation)


@router.post("/reservations/{reservation_id}/cancel", response_model=CancellationResponse)
def cancel_reservation(request: Request, reservation_id: str):
    result = request.app.state.cancel_reservation.execute(reservation_id)
    return CancellationResponse(
        reservation=ReservationResponse.from_domain(result.reservation),
        policy=result.policy,
        refund_fraction=result.refund_fraction,
        refund_amount=result.refund_amount,
    )


@router.get("/users/{user_id}/reservations", response_model=list[ReservationResponse])
def list_user_reservations(
    request: Request,
    user_id: str,
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
):
    reservations = request.app.state.list_reservations.execute(
        user_id=user_id, date_from=date_from, date_to=date_to
    )
    return [ReservationResponse.from_domain(r) for r in reservations]
