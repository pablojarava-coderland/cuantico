"""Reglas de calendario: horario, domingos, festivos y anticipación mínima."""

from datetime import datetime, timedelta

import pytest

from app.domain.calendar import BOGOTA, validate_schedulable
from app.domain.exceptions import (
    ClosedDay,
    InsufficientAdvance,
    OutsideOperatingHours,
)
from tests.conftest import FIXED_NOW


def slot(year, month, day, hour, minute=0, duration_minutes=60):
    start = datetime(year, month, day, hour, minute, tzinfo=BOGOTA)
    return start, start + timedelta(minutes=duration_minutes)


def test_sunday_is_rejected():
    with pytest.raises(ClosedDay):
        validate_schedulable(*slot(2026, 6, 21, 10))  # domingo


def test_colombian_holiday_is_rejected():
    with pytest.raises(ClosedDay):
        validate_schedulable(*slot(2026, 6, 29, 10))  # San Pedro y San Pablo


def test_before_opening_is_rejected():
    with pytest.raises(OutsideOperatingHours):
        validate_schedulable(*slot(2026, 6, 18, 6, 30))


def test_service_ending_after_closing_is_rejected():
    # Inicia dentro del horario pero terminaría 19:30: se rechaza.
    with pytest.raises(OutsideOperatingHours):
        validate_schedulable(*slot(2026, 6, 18, 18, 30))


def test_service_ending_exactly_at_closing_is_allowed():
    validate_schedulable(*slot(2026, 6, 18, 18, 0))  # termina 19:00 exacto


def test_saturday_within_hours_is_allowed():
    validate_schedulable(*slot(2026, 6, 20, 10))  # sábado


def test_exactly_two_hours_in_advance_is_allowed(container):
    start = FIXED_NOW + timedelta(hours=2)
    reservation = container.create.execute("u-ana", "svc-corte", start)
    assert reservation.start == start


def test_less_than_two_hours_in_advance_is_rejected(container):
    with pytest.raises(InsufficientAdvance):
        container.create.execute(
            "u-ana", "svc-corte", FIXED_NOW + timedelta(hours=1, minutes=59)
        )


def test_start_in_other_timezone_is_normalized_to_bogota(container):
    # 2026-06-18T13:00-03:00 == 11:00 en Bogotá: dentro de horario y con
    # más de 2h de anticipación respecto a FIXED_NOW (09:00 del 17).
    from zoneinfo import ZoneInfo

    start_foreign = datetime(2026, 6, 18, 13, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires"))
    reservation = container.create.execute("u-ana", "svc-corte", start_foreign)
    assert reservation.start.tzinfo is not None
    assert reservation.start.astimezone(BOGOTA).hour == 11
