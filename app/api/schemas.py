"""Modelos de entrada/salida HTTP (Pydantic). Separados del dominio."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.models import Reservation


class CreateReservationRequest(BaseModel):
    user_id: str
    service_id: str
    start: datetime


class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    service_id: str
    professional_id: str
    start: datetime
    end: datetime
    status: str
    price: Decimal
    cancelled_at: datetime | None = None
    refund_amount: Decimal | None = None

    @classmethod
    def from_domain(cls, reservation: Reservation) -> "ReservationResponse":
        return cls.model_validate(reservation)


class CancellationResponse(BaseModel):
    reservation: ReservationResponse
    policy: str
    refund_fraction: Decimal
    refund_amount: Decimal


class ErrorResponse(BaseModel):
    error: str
    detail: str
