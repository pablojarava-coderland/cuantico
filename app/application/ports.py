"""Puertos (interfaces) que la infraestructura debe implementar.

Los casos de uso dependen de estos Protocols, no de implementaciones:
cambiar memoria por Postgres no toca el dominio ni los casos de uso.
"""

from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol

from app.domain.models import Reservation, Service, User


class Clock(Protocol):
    """Fuente de 'ahora' inyectable: las reglas dependen del tiempo relativo."""

    def now(self) -> datetime:
        """Datetime timezone-aware en America/Bogota."""
        ...


class UserRepository(Protocol):
    def get(self, user_id: str) -> User | None: ...


class ServiceRepository(Protocol):
    def get(self, service_id: str) -> Service | None: ...


class ReservationRepository(Protocol):
    def add(self, reservation: Reservation) -> None: ...

    def get(self, reservation_id: str) -> Reservation | None: ...

    def save(self, reservation: Reservation) -> None: ...

    def for_user(self, user_id: str) -> list[Reservation]: ...

    def for_professional(self, professional_id: str) -> list[Reservation]: ...

    def atomic(self) -> AbstractContextManager[None]:
        """Exclusión mutua para operaciones de verificar-y-escribir."""
        ...
