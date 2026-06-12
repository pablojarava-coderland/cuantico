"""Casos de uso: orquestan reglas del dominio sobre los puertos."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.application.ports import (
    Clock,
    ReservationRepository,
    ServiceRepository,
    UserRepository,
)
from app.domain.calendar import to_bogota, validate_schedulable
from app.domain.exceptions import (
    ActiveLimitReached,
    AlreadyCancelled,
    InsufficientAdvance,
    OverlappingReservation,
    ReservationAlreadyStarted,
    ReservationNotFound,
    ServiceNotFound,
    UserNotFound,
)
from app.domain.models import Reservation, ReservationStatus
from app.domain.refund_policy import refund_amount, select_policy

MIN_ADVANCE = timedelta(hours=2)
MAX_ACTIVE_RESERVATIONS = 3


@dataclass(frozen=True)
class CancellationResult:
    reservation: Reservation
    policy: str
    refund_fraction: Decimal
    refund_amount: Decimal


class CreateReservation:
    def __init__(
        self,
        users: UserRepository,
        services: ServiceRepository,
        reservations: ReservationRepository,
        clock: Clock,
    ) -> None:
        self._users = users
        self._services = services
        self._reservations = reservations
        self._clock = clock

    def execute(self, user_id: str, service_id: str, start: datetime) -> Reservation:
        user = self._users.get(user_id)
        if user is None:
            raise UserNotFound(user_id)
        service = self._services.get(service_id)
        if service is None:
            raise ServiceNotFound(service_id)

        start = to_bogota(start)
        end = start + timedelta(minutes=service.duration_minutes)
        validate_schedulable(start, end)

        now = self._clock.now()
        if start - now < MIN_ADVANCE:
            raise InsufficientAdvance()

        # Verificar-y-escribir bajo exclusión mutua: evita que dos peticiones
        # concurrentes pasen ambas las validaciones de límite y solape.
        with self._reservations.atomic():
            active = [
                r
                for r in self._reservations.for_user(user.id)
                if r.is_active_future(now)
            ]
            if len(active) >= MAX_ACTIVE_RESERVATIONS:
                raise ActiveLimitReached(MAX_ACTIVE_RESERVATIONS)

            for existing in self._reservations.for_professional(service.professional_id):
                if existing.status is ReservationStatus.ACTIVE and existing.overlaps(
                    start, end
                ):
                    raise OverlappingReservation(service.professional_id)

            reservation = Reservation(
                id=uuid.uuid4().hex[:12],
                user_id=user.id,
                service_id=service.id,
                professional_id=service.professional_id,
                start=start,
                end=end,
                price=service.price,
            )
            self._reservations.add(reservation)

        return reservation


class CancelReservation:
    def __init__(
        self,
        users: UserRepository,
        services: ServiceRepository,
        reservations: ReservationRepository,
        clock: Clock,
    ) -> None:
        self._users = users
        self._services = services
        self._reservations = reservations
        self._clock = clock

    def execute(self, reservation_id: str) -> CancellationResult:
        with self._reservations.atomic():
            reservation = self._reservations.get(reservation_id)
            if reservation is None:
                raise ReservationNotFound(reservation_id)
            if reservation.status is ReservationStatus.CANCELLED:
                raise AlreadyCancelled(reservation_id)

            now = self._clock.now()
            if reservation.start <= now:
                raise ReservationAlreadyStarted()

            user = self._users.get(reservation.user_id)
            if user is None:
                raise UserNotFound(reservation.user_id)
            service = self._services.get(reservation.service_id)
            if service is None:
                raise ServiceNotFound(reservation.service_id)

            policy = select_policy(user, service)
            fraction = policy.refund_fraction(reservation.start - now)
            amount = refund_amount(reservation.price, fraction)

            reservation.status = ReservationStatus.CANCELLED
            reservation.cancelled_at = now
            reservation.refund_amount = amount
            self._reservations.save(reservation)

        return CancellationResult(
            reservation=reservation,
            policy=policy.name,
            refund_fraction=fraction,
            refund_amount=amount,
        )


class ListUserReservations:
    def __init__(self, users: UserRepository, reservations: ReservationRepository) -> None:
        self._users = users
        self._reservations = reservations

    def execute(
        self,
        user_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[Reservation]:
        if self._users.get(user_id) is None:
            raise UserNotFound(user_id)

        result = self._reservations.for_user(user_id)
        if date_from is not None:
            date_from = to_bogota(date_from)
            result = [r for r in result if r.start >= date_from]
        if date_to is not None:
            date_to = to_bogota(date_to)
            result = [r for r in result if r.start <= date_to]
        return sorted(result, key=lambda r: r.start)
