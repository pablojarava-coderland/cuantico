"""Calendario operativo: horario de atención, domingos y festivos de Colombia.

Todas las validaciones se hacen en hora local de Bogotá (America/Bogota).
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.domain.exceptions import ClosedDay, OutsideOperatingHours

BOGOTA = ZoneInfo("America/Bogota")
OPENING = time(7, 0)
CLOSING = time(19, 0)
SUNDAY = 6  # datetime.weekday()

# Festivos de Colombia 2026 (Ley Emiliani ya aplicada: los trasladables
# figuran en el lunes en que se celebran).
HOLIDAYS_2026 = frozenset(
    {
        date(2026, 1, 1),    # Año Nuevo
        date(2026, 1, 12),   # Reyes Magos (trasladado)
        date(2026, 3, 23),   # San José (trasladado)
        date(2026, 4, 2),    # Jueves Santo
        date(2026, 4, 3),    # Viernes Santo
        date(2026, 5, 1),    # Día del Trabajo
        date(2026, 5, 18),   # Ascensión (trasladado)
        date(2026, 6, 8),    # Corpus Christi (trasladado)
        date(2026, 6, 15),   # Sagrado Corazón (trasladado)
        date(2026, 6, 29),   # San Pedro y San Pablo
        date(2026, 7, 20),   # Independencia
        date(2026, 8, 7),    # Batalla de Boyacá
        date(2026, 8, 17),   # Asunción (trasladado)
        date(2026, 10, 12),  # Día de la Raza
        date(2026, 11, 2),   # Todos los Santos (trasladado)
        date(2026, 11, 16),  # Independencia de Cartagena (trasladado)
        date(2026, 12, 8),   # Inmaculada Concepción
        date(2026, 12, 25),  # Navidad
    }
)


def to_bogota(dt: datetime) -> datetime:
    """Normaliza a hora de Bogotá. Un datetime naive se asume ya en Bogotá."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=BOGOTA)
    return dt.astimezone(BOGOTA)


def validate_schedulable(start: datetime, end: datetime) -> None:
    """Valida que el intervalo [start, end] sea agendable.

    Supuesto documentado: la cita completa debe caber dentro del horario de
    atención (termina a más tardar a las 19:00 del mismo día).
    """
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start/end deben ser timezone-aware (usar to_bogota).")

    start = start.astimezone(BOGOTA)
    end = end.astimezone(BOGOTA)

    if start.weekday() == SUNDAY:
        raise ClosedDay("No se aceptan reservas los domingos.")
    if start.date() in HOLIDAYS_2026:
        raise ClosedDay(
            f"El {start.date().isoformat()} es festivo en Colombia; "
            "no se aceptan reservas."
        )
    if end.date() != start.date():
        raise OutsideOperatingHours(
            "La cita debe iniciar y terminar el mismo día."
        )
    if start.time() < OPENING or end.time() > CLOSING:
        raise OutsideOperatingHours(
            "La cita debe transcurrir completa entre 07:00 y 19:00, "
            "hora de Bogotá."
        )
