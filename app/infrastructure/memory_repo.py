"""Adaptadores de persistencia en memoria.

Suficiente para la demo; el puerto permite cambiar a una base de datos real
sin tocar dominio ni casos de uso. El lock global es la respuesta honesta a
"concurrencia básica" en un proceso único — en producción esto sería una
restricción de exclusión en la base de datos (p. ej. constraint + transacción).
"""

import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator
from zoneinfo import ZoneInfo

from app.domain.models import Reservation, Service, User

BOGOTA = ZoneInfo("America/Bogota")


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(tz=BOGOTA)


class InMemoryUsers:
    def __init__(self) -> None:
        self._items: dict[str, User] = {}

    def add(self, user: User) -> None:
        self._items[user.id] = user

    def get(self, user_id: str) -> User | None:
        return self._items.get(user_id)


class InMemoryServices:
    def __init__(self) -> None:
        self._items: dict[str, Service] = {}

    def add(self, service: Service) -> None:
        self._items[service.id] = service

    def get(self, service_id: str) -> Service | None:
        return self._items.get(service_id)


class InMemoryReservations:
    def __init__(self) -> None:
        self._items: dict[str, Reservation] = {}
        self._lock = threading.RLock()

    def add(self, reservation: Reservation) -> None:
        self._items[reservation.id] = reservation

    def get(self, reservation_id: str) -> Reservation | None:
        return self._items.get(reservation_id)

    def save(self, reservation: Reservation) -> None:
        self._items[reservation.id] = reservation

    def for_user(self, user_id: str) -> list[Reservation]:
        return [r for r in self._items.values() if r.user_id == user_id]

    def for_professional(self, professional_id: str) -> list[Reservation]:
        return [r for r in self._items.values() if r.professional_id == professional_id]

    @contextmanager
    def atomic(self) -> Iterator[None]:
        with self._lock:
            yield
