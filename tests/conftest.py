"""Fixtures compartidas: reloj falso y contenedor con datos conocidos.

FIXED_NOW = miércoles 2026-06-17 09:00, hora de Bogotá (día hábil normal,
lejos de festivos). Todas las pruebas de reglas temporales parten de ahí.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.application.use_cases import (
    CancelReservation,
    CreateReservation,
    ListUserReservations,
)
from app.domain.models import Plan, Service, User
from app.infrastructure.memory_repo import (
    InMemoryReservations,
    InMemoryServices,
    InMemoryUsers,
)

BOGOTA = ZoneInfo("America/Bogota")
FIXED_NOW = datetime(2026, 6, 17, 9, 0, tzinfo=BOGOTA)


class FakeClock:
    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def set(self, now: datetime) -> None:
        self._now = now


@dataclass
class Container:
    users: InMemoryUsers
    services: InMemoryServices
    reservations: InMemoryReservations
    clock: FakeClock
    create: CreateReservation
    cancel: CancelReservation
    list_for_user: ListUserReservations


@pytest.fixture
def container() -> Container:
    users = InMemoryUsers()
    services = InMemoryServices()
    reservations = InMemoryReservations()
    clock = FakeClock()

    users.add(User(id="u-ana", name="Ana", plan=Plan.STANDARD))
    users.add(User(id="u-carlos", name="Carlos", plan=Plan.PREMIUM))

    services.add(
        Service(
            id="svc-corte",
            name="Corte",
            duration_minutes=30,
            price=Decimal("40000"),
            professional_id="p-laura",
        )
    )
    services.add(
        Service(
            id="svc-tinte",
            name="Tinte",
            duration_minutes=90,
            price=Decimal("150000"),
            professional_id="p-laura",
        )
    )
    services.add(
        Service(
            id="svc-masaje",
            name="Masaje",
            duration_minutes=60,
            price=Decimal("90000"),
            professional_id="p-mario",
        )
    )
    services.add(
        Service(
            id="svc-spa",
            name="Spa",
            duration_minutes=120,
            price=Decimal("200000"),
            professional_id="p-mario",
            non_refundable=True,
        )
    )

    return Container(
        users=users,
        services=services,
        reservations=reservations,
        clock=clock,
        create=CreateReservation(users, services, reservations, clock),
        cancel=CancelReservation(users, services, reservations, clock),
        list_for_user=ListUserReservations(users, reservations),
    )
