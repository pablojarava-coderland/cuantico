"""Composición de la aplicación: wiring de dependencias y manejo de errores.

`build_app` recibe el reloj y la ruta del seed para que las pruebas puedan
inyectar un reloj fijo y datos controlados.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.application.ports import Clock
from app.application.use_cases import (
    CancelReservation,
    CreateReservation,
    ListUserReservations,
)
from app.domain.exceptions import DomainError, NotFoundError, RuleViolation
from app.infrastructure.memory_repo import (
    InMemoryReservations,
    InMemoryServices,
    InMemoryUsers,
    SystemClock,
)
from app.infrastructure.seed_loader import load_seed

DEFAULT_SEED = Path(__file__).resolve().parents[2] / "data" / "seed.json"


def _status_code(exc: DomainError) -> int:
    if isinstance(exc, NotFoundError):
        return 404
    if isinstance(exc, RuleViolation):
        return 409
    return 400


def build_app(seed_path: Path = DEFAULT_SEED, clock: Clock | None = None) -> FastAPI:
    clock = clock or SystemClock()
    users = InMemoryUsers()
    services = InMemoryServices()
    reservations = InMemoryReservations()
    seed_report = load_seed(seed_path, users, services, reservations)

    app = FastAPI(
        title="Servicio de Reservas",
        description="Prueba técnica — gestión de reservas de citas.",
        version="0.1.0",
    )
    app.state.seed_report = seed_report
    app.state.create_reservation = CreateReservation(users, services, reservations, clock)
    app.state.cancel_reservation = CancelReservation(users, services, reservations, clock)
    app.state.list_reservations = ListUserReservations(users, reservations)

    @app.exception_handler(DomainError)
    def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=_status_code(exc),
            content={"error": exc.code, "detail": str(exc)},
        )

    app.include_router(router)
    return app


app = build_app()
