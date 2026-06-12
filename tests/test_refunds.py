"""Tablas de reembolso: estándar, premium y no reembolsable.

Las políticas son funciones puras: se prueban con la tabla completa,
incluyendo los límites exactos (24h, 4h, 1h), que caen en el tramo
menos generoso (decisión documentada en el README).
"""

from datetime import timedelta
from decimal import Decimal

import pytest

from app.domain.models import Plan, Service, User
from app.domain.refund_policy import (
    NonRefundablePolicy,
    PremiumPolicy,
    StandardPolicy,
    refund_amount,
    select_policy,
)


@pytest.mark.parametrize(
    ("hours_before", "expected"),
    [
        (25, Decimal("1")),
        (24.01, Decimal("1")),
        (24, Decimal("0.5")),  # límite exacto: tramo menos generoso
        (12, Decimal("0.5")),
        (4.01, Decimal("0.5")),
        (4, Decimal("0")),  # límite exacto
        (1, Decimal("0")),
    ],
)
def test_standard_refund_table(hours_before, expected):
    fraction = StandardPolicy().refund_fraction(timedelta(hours=hours_before))
    assert fraction == expected


@pytest.mark.parametrize(
    ("hours_before", "expected"),
    [
        (25, Decimal("1")),
        (5, Decimal("1")),
        (4.01, Decimal("1")),
        (4, Decimal("0.5")),  # límite exacto
        (2, Decimal("0.5")),
        (1.01, Decimal("0.5")),
        (1, Decimal("0")),  # límite exacto
        (0.5, Decimal("0")),
    ],
)
def test_premium_refund_table(hours_before, expected):
    fraction = PremiumPolicy().refund_fraction(timedelta(hours=hours_before))
    assert fraction == expected


@pytest.mark.parametrize("hours_before", [100, 24, 4, 1, 0.1])
def test_non_refundable_is_always_zero(hours_before):
    fraction = NonRefundablePolicy().refund_fraction(timedelta(hours=hours_before))
    assert fraction == Decimal("0")


def _service(non_refundable: bool) -> Service:
    return Service(
        id="s",
        name="s",
        duration_minutes=30,
        price=Decimal("100"),
        professional_id="p",
        non_refundable=non_refundable,
    )


def test_non_refundable_overrides_premium_plan():
    premium_user = User(id="u", name="u", plan=Plan.PREMIUM)
    policy = select_policy(premium_user, _service(non_refundable=True))
    assert policy.name == "non_refundable"


def test_policy_selection_by_plan():
    assert select_policy(User(id="u", name="u"), _service(False)).name == "standard"
    assert (
        select_policy(User(id="u", name="u", plan=Plan.PREMIUM), _service(False)).name
        == "premium"
    )


def test_refund_amount_rounds_to_cents():
    assert refund_amount(Decimal("33335"), Decimal("0.5")) == Decimal("16667.50")
