"""Entidades del dominio. Sin dependencias de framework ni de I/O."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class Plan(str, Enum):
    STANDARD = "standard"
    PREMIUM = "premium"


class ReservationStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class User:
    id: str
    name: str
    plan: Plan = Plan.STANDARD


@dataclass(frozen=True)
class Service:
    id: str
    name: str
    duration_minutes: int
    price: Decimal
    professional_id: str
    non_refundable: bool = False


@dataclass
class Reservation:
    id: str
    user_id: str
    service_id: str
    professional_id: str
    start: datetime  # siempre timezone-aware en America/Bogota
    end: datetime
    price: Decimal  # precio congelado al momento de reservar
    status: ReservationStatus = ReservationStatus.ACTIVE
    cancelled_at: datetime | None = None
    refund_amount: Decimal | None = None

    def overlaps(self, start: datetime, end: datetime) -> bool:
        """Solape de intervalos semiabiertos [start, end): tocar bordes no solapa."""
        return self.start < end and start < self.end

    def is_active_future(self, now: datetime) -> bool:
        """Cuenta para el límite de 3 reservas: no cancelada y aún no iniciada."""
        return self.status is ReservationStatus.ACTIVE and self.start > now
