"""Carga del seed: formatos de fecha mezclados y registros corruptos."""

from datetime import datetime
from pathlib import Path

from app.domain.calendar import BOGOTA
from app.domain.models import Plan
from app.infrastructure.memory_repo import (
    InMemoryReservations,
    InMemoryServices,
    InMemoryUsers,
)
from app.infrastructure.seed_loader import load_seed

SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed.json"


def load():
    users, services, reservations = (
        InMemoryUsers(),
        InMemoryServices(),
        InMemoryReservations(),
    )
    report = load_seed(SEED_PATH, users, services, reservations)
    return users, services, reservations, report


def test_seed_loads_expected_counts():
    _, _, _, report = load()
    assert report.users_loaded == 3
    assert report.services_loaded == 4
    # r-006 no tiene fecha: se descarta, quedan 6 de 7.
    assert report.reservations_loaded == 6


def test_broken_records_are_reported_not_fatal():
    _, _, reservations, report = load()
    assert reservations.get("r-006") is None
    assert any("r-006" in w for w in report.warnings)
    assert any("u-diana" in w for w in report.warnings)  # sin plan


def test_local_date_format_is_parsed_as_bogota():
    _, _, reservations, _ = load()
    r = reservations.get("r-002")  # "23/06/2026 14:30"
    assert r is not None
    assert r.start == datetime(2026, 6, 23, 14, 30, tzinfo=BOGOTA)


def test_naive_iso_date_is_assumed_bogota():
    _, _, reservations, _ = load()
    r = reservations.get("r-003")  # "2026-06-20T09:00:00" sin zona
    assert r is not None
    assert r.start == datetime(2026, 6, 20, 9, 0, tzinfo=BOGOTA)


def test_user_without_plan_defaults_to_standard():
    users, _, _, _ = load()
    diana = users.get("u-diana")
    assert diana is not None
    assert diana.plan is Plan.STANDARD


def test_reservation_end_is_derived_from_service_duration():
    _, services, reservations, _ = load()
    r = reservations.get("r-001")  # svc-corte: 30 minutos
    assert (r.end - r.start).total_seconds() == 30 * 60
