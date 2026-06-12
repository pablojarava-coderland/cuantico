"""Carga tolerante de data/seed.json.

El enunciado dice que los datos traen inconsistencias intencionales (formatos
de fecha mezclados, campos faltantes). Estrategia:

- Fechas: se aceptan ISO 8601 (con o sin offset; naive ⇒ se asume Bogotá)
  y el formato local DD/MM/YYYY HH:MM. Cualquier otro formato invalida el
  registro.
- Campos opcionales con default razonable (plan ⇒ standard, status ⇒ active,
  non_refundable ⇒ false) generan una advertencia, no un descarte.
- Registros sin campos esenciales (fecha, referencias) se descartan y se
  reportan: preferimos arrancar con datos parciales y un reporte claro a
  fallar todo el arranque por un registro corrupto.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.domain.calendar import to_bogota
from app.domain.models import Plan, Reservation, ReservationStatus, Service, User
from app.infrastructure.memory_repo import (
    InMemoryReservations,
    InMemoryServices,
    InMemoryUsers,
)

LOCAL_FORMAT = "%d/%m/%Y %H:%M"


@dataclass
class SeedReport:
    users_loaded: int = 0
    services_loaded: int = 0
    reservations_loaded: int = 0
    warnings: list[str] = field(default_factory=list)


def parse_datetime(value: object) -> datetime:
    """Acepta ISO 8601 y DD/MM/YYYY HH:MM; normaliza a America/Bogota."""
    if not isinstance(value, str):
        raise ValueError(f"fecha no es texto: {value!r}")
    try:
        return to_bogota(datetime.fromisoformat(value))
    except ValueError:
        pass
    try:
        return to_bogota(datetime.strptime(value, LOCAL_FORMAT))
    except ValueError:
        raise ValueError(f"formato de fecha no reconocido: {value!r}")


def load_seed(
    path: Path,
    users: InMemoryUsers,
    services: InMemoryServices,
    reservations: InMemoryReservations,
) -> SeedReport:
    report = SeedReport()
    raw = json.loads(path.read_text(encoding="utf-8"))

    for item in raw.get("users", []):
        user_id, name = item.get("id"), item.get("name")
        if not user_id or not name:
            report.warnings.append(f"usuario omitido (falta id o name): {item!r}")
            continue
        plan_raw = item.get("plan")
        if plan_raw is None:
            report.warnings.append(
                f"usuario '{user_id}': sin campo 'plan', se asume 'standard'."
            )
            plan = Plan.STANDARD
        else:
            try:
                plan = Plan(plan_raw)
            except ValueError:
                report.warnings.append(
                    f"usuario '{user_id}': plan desconocido {plan_raw!r}, "
                    "se asume 'standard'."
                )
                plan = Plan.STANDARD
        users.add(User(id=user_id, name=name, plan=plan))
        report.users_loaded += 1

    for item in raw.get("services", []):
        service_id = item.get("id")
        required = ("name", "duration_minutes", "price", "professional_id")
        missing = [f for f in required if item.get(f) is None]
        if not service_id or missing:
            report.warnings.append(
                f"servicio omitido (faltan campos {missing}): {item!r}"
            )
            continue
        try:
            price = Decimal(str(item["price"]))
        except InvalidOperation:
            report.warnings.append(
                f"servicio '{service_id}' omitido: precio inválido {item['price']!r}"
            )
            continue
        services.add(
            Service(
                id=service_id,
                name=item["name"],
                duration_minutes=int(item["duration_minutes"]),
                price=price,
                professional_id=item["professional_id"],
                non_refundable=bool(item.get("non_refundable", False)),
            )
        )
        report.services_loaded += 1

    for item in raw.get("reservations", []):
        res_id = item.get("id")
        if not res_id:
            report.warnings.append(f"reserva omitida (sin id): {item!r}")
            continue
        service = services.get(item.get("service_id", ""))
        if service is None:
            report.warnings.append(
                f"reserva '{res_id}' omitida: servicio desconocido "
                f"{item.get('service_id')!r}"
            )
            continue
        if users.get(item.get("user_id", "")) is None:
            report.warnings.append(
                f"reserva '{res_id}' omitida: usuario desconocido "
                f"{item.get('user_id')!r}"
            )
            continue
        try:
            start = parse_datetime(item.get("start"))
        except ValueError as exc:
            report.warnings.append(f"reserva '{res_id}' omitida: {exc}")
            continue

        status_raw = item.get("status", "active")
        try:
            status = ReservationStatus(status_raw)
        except ValueError:
            report.warnings.append(
                f"reserva '{res_id}': status desconocido {status_raw!r}, "
                "se asume 'active'."
            )
            status = ReservationStatus.ACTIVE

        reservations.add(
            Reservation(
                id=res_id,
                user_id=item["user_id"],
                service_id=service.id,
                professional_id=service.professional_id,
                start=start,
                end=start + timedelta(minutes=service.duration_minutes),
                price=service.price,
                status=status,
            )
        )
        report.reservations_loaded += 1

    return report
