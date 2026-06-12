"""Casos de uso: solape, límite de activas, cancelación y concurrencia básica."""

import threading
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.calendar import BOGOTA
from app.domain.exceptions import (
    ActiveLimitReached,
    AlreadyCancelled,
    OverlappingReservation,
    ReservationAlreadyStarted,
    ReservationNotFound,
    UserNotFound,
)
from app.domain.models import Reservation, ReservationStatus
from tests.conftest import FIXED_NOW

THURSDAY_10 = datetime(2026, 6, 18, 10, 0, tzinfo=BOGOTA)


# --- Solape por profesional -------------------------------------------------


def test_overlapping_reservation_same_professional_is_rejected(container):
    container.create.execute("u-ana", "svc-corte", THURSDAY_10)
    with pytest.raises(OverlappingReservation):
        container.create.execute(
            "u-carlos", "svc-corte", THURSDAY_10 + timedelta(minutes=15)
        )


def test_adjacent_reservation_same_professional_is_allowed(container):
    # [10:00, 10:30) y [10:30, 11:00): tocar el borde no es solape.
    container.create.execute("u-ana", "svc-corte", THURSDAY_10)
    reservation = container.create.execute(
        "u-carlos", "svc-corte", THURSDAY_10 + timedelta(minutes=30)
    )
    assert reservation.status is ReservationStatus.ACTIVE


def test_same_slot_different_professional_is_allowed(container):
    container.create.execute("u-ana", "svc-corte", THURSDAY_10)  # p-laura
    reservation = container.create.execute("u-carlos", "svc-masaje", THURSDAY_10)  # p-mario
    assert reservation.professional_id == "p-mario"


def test_cancelled_reservation_does_not_block_slot(container):
    first = container.create.execute("u-ana", "svc-corte", THURSDAY_10)
    container.cancel.execute(first.id)
    reservation = container.create.execute("u-carlos", "svc-corte", THURSDAY_10)
    assert reservation.status is ReservationStatus.ACTIVE


# --- Límite de 3 reservas activas -------------------------------------------


def test_fourth_active_reservation_is_rejected(container):
    for hour in (10, 11, 12):
        container.create.execute(
            "u-ana", "svc-corte", THURSDAY_10.replace(hour=hour)
        )
    with pytest.raises(ActiveLimitReached):
        container.create.execute("u-ana", "svc-corte", THURSDAY_10.replace(hour=13))


def test_cancelled_reservations_do_not_count_toward_limit(container):
    reservations = [
        container.create.execute("u-ana", "svc-corte", THURSDAY_10.replace(hour=h))
        for h in (10, 11, 12)
    ]
    container.cancel.execute(reservations[0].id)
    fourth = container.create.execute(
        "u-ana", "svc-corte", THURSDAY_10.replace(hour=13)
    )
    assert fourth.status is ReservationStatus.ACTIVE


def test_past_reservations_do_not_count_toward_limit(container):
    past = Reservation(
        id="r-past",
        user_id="u-ana",
        service_id="svc-corte",
        professional_id="p-laura",
        start=FIXED_NOW - timedelta(days=7),
        end=FIXED_NOW - timedelta(days=7) + timedelta(minutes=30),
        price=Decimal("40000"),
    )
    container.reservations.add(past)
    for hour in (10, 11, 12):  # aún caben 3 activas futuras
        container.create.execute("u-ana", "svc-corte", THURSDAY_10.replace(hour=hour))


# --- Cancelación -------------------------------------------------------------


def test_cancel_unknown_reservation(container):
    with pytest.raises(ReservationNotFound):
        container.cancel.execute("no-existe")


def test_cancel_twice_is_rejected_and_refund_not_duplicated(container):
    reservation = container.create.execute("u-ana", "svc-corte", THURSDAY_10)
    first = container.cancel.execute(reservation.id)
    with pytest.raises(AlreadyCancelled):
        container.cancel.execute(reservation.id)
    assert reservation.refund_amount == first.refund_amount


def test_cancel_already_started_reservation_is_rejected(container):
    started = Reservation(
        id="r-started",
        user_id="u-ana",
        service_id="svc-corte",
        professional_id="p-laura",
        start=FIXED_NOW - timedelta(minutes=10),
        end=FIXED_NOW + timedelta(minutes=20),
        price=Decimal("40000"),
    )
    container.reservations.add(started)
    with pytest.raises(ReservationAlreadyStarted):
        container.cancel.execute("r-started")


def test_standard_user_late_cancellation_refunds_half(container):
    # Reserva jueves 10:00; cancela el mismo jueves a las 04:00 (6h antes).
    reservation = container.create.execute("u-ana", "svc-corte", THURSDAY_10)
    container.clock.set(THURSDAY_10 - timedelta(hours=6))
    result = container.cancel.execute(reservation.id)
    assert result.policy == "standard"
    assert result.refund_fraction == Decimal("0.5")
    assert result.refund_amount == Decimal("20000.00")


def test_premium_user_keeps_full_refund_until_4h(container):
    reservation = container.create.execute("u-carlos", "svc-masaje", THURSDAY_10)
    container.clock.set(THURSDAY_10 - timedelta(hours=6))
    result = container.cancel.execute(reservation.id)
    assert result.policy == "premium"
    assert result.refund_amount == Decimal("90000.00")


def test_non_refundable_service_cancels_with_zero_refund(container):
    # Premium + cancelación con 40h de anticipación: aun así 0 por ser
    # servicio no reembolsable. La cancelación sí procede.
    reservation = container.create.execute("u-carlos", "svc-spa", THURSDAY_10)
    result = container.cancel.execute(reservation.id)
    assert result.policy == "non_refundable"
    assert result.refund_amount == Decimal("0.00")
    assert result.reservation.status is ReservationStatus.CANCELLED


# --- Listado -----------------------------------------------------------------


def test_list_reservations_filters_by_range_and_sorts(container):
    r1 = container.create.execute("u-ana", "svc-corte", THURSDAY_10.replace(hour=12))
    r2 = container.create.execute("u-ana", "svc-corte", THURSDAY_10)
    container.create.execute(
        "u-ana", "svc-corte", THURSDAY_10 + timedelta(days=7)
    )  # fuera del rango

    result = container.list_for_user.execute(
        "u-ana",
        date_from=THURSDAY_10.replace(hour=7),
        date_to=THURSDAY_10.replace(hour=18),
    )
    assert [r.id for r in result] == [r2.id, r1.id]


def test_list_reservations_unknown_user(container):
    with pytest.raises(UserNotFound):
        container.list_for_user.execute("no-existe")


# --- Concurrencia básica -----------------------------------------------------


def test_concurrent_booking_same_slot_only_one_wins(container):
    """Dos peticiones simultáneas por el mismo cupo: exactamente una gana."""
    results: list = []
    barrier = threading.Barrier(2)

    def book(user_id: str) -> None:
        barrier.wait()
        try:
            results.append(container.create.execute(user_id, "svc-corte", THURSDAY_10))
        except OverlappingReservation as exc:
            results.append(exc)

    threads = [
        threading.Thread(target=book, args=(uid,)) for uid in ("u-ana", "u-carlos")
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, OverlappingReservation)]
    assert len(successes) == 1
    assert len(failures) == 1
