"""Errores de negocio del dominio de reservas.

La capa API los traduce a códigos HTTP; el dominio solo conoce reglas.
"""


class DomainError(Exception):
    """Base de todos los errores de negocio."""

    code = "domain_error"


class NotFoundError(DomainError):
    code = "not_found"


class UserNotFound(NotFoundError):
    code = "user_not_found"

    def __init__(self, user_id: str) -> None:
        super().__init__(f"El usuario '{user_id}' no existe.")


class ServiceNotFound(NotFoundError):
    code = "service_not_found"

    def __init__(self, service_id: str) -> None:
        super().__init__(f"El servicio '{service_id}' no existe.")


class ReservationNotFound(NotFoundError):
    code = "reservation_not_found"

    def __init__(self, reservation_id: str) -> None:
        super().__init__(f"La reserva '{reservation_id}' no existe.")


class RuleViolation(DomainError):
    """Una regla de negocio impide la operación."""

    code = "rule_violation"


class ClosedDay(RuleViolation):
    code = "closed_day"


class OutsideOperatingHours(RuleViolation):
    code = "outside_operating_hours"


class InsufficientAdvance(RuleViolation):
    code = "insufficient_advance"

    def __init__(self) -> None:
        super().__init__(
            "La reserva debe crearse con al menos 2 horas de anticipación."
        )


class OverlappingReservation(RuleViolation):
    code = "overlapping_reservation"

    def __init__(self, professional_id: str) -> None:
        super().__init__(
            f"El profesional '{professional_id}' ya tiene una reserva que se "
            "solapa con el horario solicitado."
        )


class ActiveLimitReached(RuleViolation):
    code = "active_limit_reached"

    def __init__(self, limit: int) -> None:
        super().__init__(
            f"El usuario ya tiene {limit} reservas activas; no puede crear más."
        )


class AlreadyCancelled(RuleViolation):
    code = "already_cancelled"

    def __init__(self, reservation_id: str) -> None:
        super().__init__(f"La reserva '{reservation_id}' ya está cancelada.")


class ReservationAlreadyStarted(RuleViolation):
    code = "reservation_already_started"

    def __init__(self) -> None:
        super().__init__(
            "No se puede cancelar una reserva que ya inició o finalizó."
        )
