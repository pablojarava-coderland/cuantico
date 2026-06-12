"""Políticas de reembolso (patrón Strategy).

Tres políticas descritas por el negocio:
- Estándar:        >24h → 100%, (4h, 24h] → 50%, ≤4h → 0%
- Premium:         >4h → 100%,  (1h, 4h]  → 50%, ≤1h → 0%
- No reembolsable: siempre 0%, sin importar plan ni anticipación.

Supuesto documentado: los límites exactos (24h, 4h, 1h) caen en el tramo
menos generoso, leyendo literalmente "más de 24 horas" como estricto.
"""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from app.domain.models import Plan, Service, User

ZERO = Decimal("0")
HALF = Decimal("0.5")
FULL = Decimal("1")


class RefundPolicy(Protocol):
    name: str

    def refund_fraction(self, time_until_start: timedelta) -> Decimal: ...


class StandardPolicy:
    name = "standard"

    def refund_fraction(self, time_until_start: timedelta) -> Decimal:
        if time_until_start > timedelta(hours=24):
            return FULL
        if time_until_start > timedelta(hours=4):
            return HALF
        return ZERO


class PremiumPolicy:
    name = "premium"

    def refund_fraction(self, time_until_start: timedelta) -> Decimal:
        if time_until_start > timedelta(hours=4):
            return FULL
        if time_until_start > timedelta(hours=1):
            return HALF
        return ZERO


class NonRefundablePolicy:
    name = "non_refundable"

    def refund_fraction(self, time_until_start: timedelta) -> Decimal:
        return ZERO


_STANDARD = StandardPolicy()
_PREMIUM = PremiumPolicy()
_NON_REFUNDABLE = NonRefundablePolicy()


def select_policy(user: User, service: Service) -> RefundPolicy:
    """El servicio no reembolsable prima sobre cualquier plan."""
    if service.non_refundable:
        return _NON_REFUNDABLE
    if user.plan is Plan.PREMIUM:
        return _PREMIUM
    return _STANDARD


def refund_amount(price: Decimal, fraction: Decimal) -> Decimal:
    return (price * fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
