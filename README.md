# Servicio de Reservas — Prueba Técnica

API HTTP para crear, cancelar y listar reservas de citas, con cálculo de
reembolso según reglas de negocio. Python 3.12 + FastAPI, con arquitectura
hexagonal ligera y persistencia en memoria sembrada desde `data/seed.json`.

## Cómo correrlo

Con [uv](https://docs.astral.sh/uv/) (recomendado):

```bash
uv sync                                  # crea el entorno e instala dependencias
uv run uvicorn app.api.main:app --reload # levanta la API en http://127.0.0.1:8000
uv run pytest -v                         # corre las pruebas
```

Con pip clásico:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install fastapi 'uvicorn[standard]' pytest httpx
uvicorn app.api.main:app --reload
pytest -v
```

Documentación interactiva (OpenAPI) en `http://127.0.0.1:8000/docs`.

### Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/reservations` | Crea una reserva `{user_id, service_id, start}` |
| `POST` | `/reservations/{id}/cancel` | Cancela y devuelve el reembolso calculado |
| `GET` | `/users/{user_id}/reservations?from=&to=` | Lista reservas del usuario en un rango |
| `GET` | `/health` | Estado + advertencias de carga del seed |

Ejemplos:

```bash
# Crear (jueves hábil, 10:00 Bogotá)
curl -s -X POST localhost:8000/reservations \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "u-diana", "service_id": "svc-corte", "start": "2026-06-18T10:00:00-05:00"}'

# Cancelar
curl -s -X POST localhost:8000/reservations/<id>/cancel

# Listar en rango
curl -s 'localhost:8000/users/u-ana/reservations?from=2026-06-19T00:00:00&to=2026-06-30T23:59:00'
```

## Arquitectura

Hexagonal (puertos y adaptadores) en versión ligera, proporcional al tamaño
del problema:

```
app/
├── domain/          # Reglas puras: sin framework, sin I/O
│   ├── models.py        # User, Service, Reservation
│   ├── calendar.py      # Horario, domingos, festivos CO 2026
│   ├── refund_policy.py # Strategy: standard / premium / non_refundable
│   └── exceptions.py    # Errores de negocio tipados
├── application/     # Casos de uso sobre puertos (Protocols)
│   ├── ports.py         # Clock, UserRepository, ServiceRepository, ReservationRepository
│   └── use_cases.py     # CreateReservation, CancelReservation, ListUserReservations
├── infrastructure/  # Adaptadores: memoria + carga tolerante del seed
└── api/             # FastAPI: rutas delgadas, schemas, mapeo error→HTTP
```

### Decisiones técnicas (qué y por qué)

- **FastAPI + Pydantic**: validación de entrada tipada y documentación
  OpenAPI gratis, útil para evaluar la API sin Postman.
- **Reglas en el dominio puro**: cada regla del enunciado vive en una función
  o clase pequeña y testeable sin levantar el servidor. La tabla de
  reembolsos es un Strategy (`refund_policy.py`) porque el negocio describe
  literalmente tres políticas; agregar una cuarta (p. ej. plan corporativo)
  es una clase nueva, sin tocar la cancelación.
- **Reloj inyectable (`Clock`)**: todas las reglas son relativas a "ahora"
  (2h de anticipación, ventanas de 24h/4h/1h). Inyectar el reloj hace esas
  reglas deterministas en pruebas, sin mocks de `datetime`.
- **Persistencia en memoria detrás de un puerto**: una base de datos real no
  demostraría más arquitectura en una demo y sí costaría tiempo del budget.
  Cambiar a Postgres = implementar `ReservationRepository` con SQL; dominio
  y casos de uso no cambian.
- **Dinero con `Decimal`**: nunca float para montos; redondeo a centavos con
  `ROUND_HALF_UP` explícito.
- **Concurrencia básica**: las operaciones de verificar-y-escribir (límite
  de activas + solape + inserción) corren bajo exclusión mutua del
  repositorio (`atomic()`), con prueba que dispara dos hilos por el mismo
  cupo y verifica que exactamente uno gana. En producción esto sería una
  transacción con constraint de exclusión en la base de datos (p. ej.
  `EXCLUDE USING gist` en Postgres) — el lock global en memoria es la
  respuesta honesta y correcta para un proceso único.

## Supuestos (ambigüedades resueltas y documentadas)

1. **La cita completa debe caber en el horario**: inicia ≥ 07:00 y termina
   ≤ 19:00 del mismo día. Un tinte de 90 min a las 18:30 se rechaza, porque
   atendería fuera del horario de operación.
2. **Anticipación mínima**: exactamente 2h antes se acepta (`>=`).
3. **Límites de reembolso**: leyendo literalmente "más de 24 horas", los
   límites exactos caen en el tramo menos generoso: 24h exactas → 50%,
   4h exactas → 0% (estándar); 4h exactas → 50%, 1h exacta → 0% (premium).
4. **"Reserva activa"** para el límite de 3: no cancelada **y** con inicio
   futuro. Las pasadas y las canceladas no cuentan.
5. **Solape**: intervalos semiabiertos `[start, end)` — una cita que termina
   10:30 no choca con otra que empieza 10:30.
6. **Cancelar reservas pasadas o ya canceladas**: se rechaza con error
   explícito (no hay nada razonable que reembolsar dos veces o a posteriori).
7. **La cancelación no está sujeta al horario de operación**: se puede
   cancelar un domingo a medianoche; el horario restringe las *citas*.
8. **Fechas de entrada**: cualquier timezone se normaliza a Bogotá antes de
   validar; un datetime sin zona se asume hora de Bogotá (documentado en
   `calendar.to_bogota`).
9. **Precio congelado**: la reserva copia el precio del servicio al crearse;
   un cambio de tarifa posterior no afecta reembolsos de reservas existentes.

## Datos de prueba (`data/seed.json`)

El enunciado anuncia datos con inconsistencias intencionales pero el archivo
no venía adjunto (se confirmó con el equipo), así que lo construí con las
inconsistencias que el enunciado describe:

- `r-002` usa formato local `DD/MM/YYYY HH:MM`.
- `r-003` es ISO sin zona horaria (se asume Bogotá).
- `r-006` no tiene fecha → se descarta y se reporta.
- `u-diana` no tiene campo `plan` → default `standard` con advertencia.

Estrategia de carga (en `seed_loader.py`): registros con defaults razonables
se cargan con advertencia; registros sin campos esenciales se descartan y se
reportan. El arranque nunca falla por un registro corrupto, y las
advertencias quedan visibles en `GET /health`.

## Pruebas

33 pruebas en 4 archivos (mínimo pedido: 5). Qué se prueba y por qué:

- `test_refunds.py` — tabla completa de reembolsos parametrizada, incluyendo
  los límites exactos (24h/4h/1h) y la prioridad de `non_refundable` sobre
  premium. Es la lógica con más riesgo de plata real.
- `test_calendar_rules.py` — domingos, festivos, bordes del horario (terminar
  19:00 exacto vs 19:30), anticipación de 2h exactas, y normalización de
  zonas horarias distintas a Bogotá.
- `test_use_cases.py` — solape por profesional (incluye bordes adyacentes y
  cupo liberado por cancelación), límite de 3 activas (canceladas y pasadas
  no cuentan), doble cancelación, cancelación de reserva iniciada, y carrera
  de dos hilos por el mismo cupo.
- `test_seed_loader.py` / `test_api.py` — datos sucios del seed y humo HTTP
  (wiring, serialización, mapeo de errores a 404/409).

## Qué quedó por fuera (y por qué)

- **Base de datos real**: el puerto está definido; implementarlo no agrega
  señal en 4–6h. Primera mejora en producción.
- **Autenticación/autorización**: fuera del alcance del enunciado.
- **Festivos más allá de 2026**: el enunciado permite lista fija de 2026; en
  producción usaría una librería tipo `holidays` o un servicio de calendario.
- **Paginación del listado**: irrelevante a esta escala.
- **Reagendamiento, recordatorios, pagos**: no pedidos.

## Qué haría diferente con más tiempo

- Postgres con constraint de exclusión por profesional (`tstzrange` +
  `EXCLUDE USING gist`) para que el no-solape lo garantice la base de datos
  incluso con múltiples réplicas del servicio.
- Idempotency keys en la creación (reintentos seguros desde el cliente).
- Eventos de dominio (reserva creada/cancelada) para desacoplar
  notificaciones y auditoría.
- CI (GitHub Actions) con lint (ruff) + pruebas.
- Logging estructurado y trazas de cada decisión de reembolso.

## Notas sobre uso de IA

Ver [NOTAS.md](NOTAS.md).
