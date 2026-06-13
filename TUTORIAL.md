# Tutorial — Entender este proyecto a fondo

> Documento de estudio para ti (el candidato). No es un entregable; sirve para
> que puedas **caminar por la solución**, **defender cada decisión** y **hacer
> una modificación en vivo** en la entrevista. Léelo de arriba hacia abajo.

---

## 0. La idea en una frase

Es un servicio que **crea, cancela y lista reservas de citas**, aplicando
reglas de negocio reales (horarios, festivos, anticipación, solapes, límites,
reembolsos). Lo construimos con **arquitectura hexagonal ligera**: las reglas
viven en un núcleo puro, y todo lo "externo" (HTTP, almacenamiento, reloj)
son piezas intercambiables enchufadas alrededor.

Si solo recuerdas una cosa para la entrevista, que sea esta:

> **El dominio no sabe que existe FastAPI, ni JSON, ni la hora del sistema.
> Solo conoce reglas. Todo lo demás se le inyecta.**

---

## 1. El paradigma: arquitectura hexagonal (puertos y adaptadores)

### El problema que resuelve

En una arquitectura típica "por capas" mal hecha, las reglas de negocio
terminan mezcladas con detalles de framework: validas un horario dentro de un
controlador de FastAPI, lees la fecha directo de un JSON, llamas a
`datetime.now()` en medio de la lógica. Resultado: para probar una regla
tienes que levantar un servidor, y para cambiar de base de datos tocas el
código de negocio.

### La solución

Se invierte la dependencia. Dibujado:

```
          (entrada)                                  (salida)
        ┌───────────┐                          ┌──────────────────┐
        │  FastAPI  │                          │  Repos en memoria │
        │  (api/)   │                          │  Reloj del sistema│
        └─────┬─────┘                          └─────────▲────────┘
              │ llama                                     │ implementa
              ▼                                           │
        ┌─────────────────────────────────────────────────────────┐
        │                    application/                          │
        │     Casos de uso  ──────depende de────►  Puertos         │
        │  (CreateReservation, ...)            (Protocols: Clock,  │
        │                                       Repositories)      │
        └───────────────────────────┬─────────────────────────────┘
                                     │ usa
                                     ▼
        ┌─────────────────────────────────────────────────────────┐
        │                       domain/                            │
        │   Reglas PURAS: models, calendar, refund_policy          │
        │   (cero imports de framework, cero I/O)                  │
        └─────────────────────────────────────────────────────────┘
```

### La regla de oro: las flechas de dependencia apuntan hacia adentro

- `domain/` no importa **nada** de las otras capas. Es el centro.
- `application/` importa de `domain/`, y define **puertos** (interfaces) que
  describen lo que necesita del mundo exterior, sin saber cómo se implementan.
- `infrastructure/` y `api/` son **adaptadores**: dependen hacia adentro,
  implementan los puertos y traducen entre el mundo exterior y el dominio.

**Cómo lo verificas tú mismo (y un buen punto para la entrevista):**

```bash
# Si esto no devuelve NADA, el dominio está limpio de framework:
grep -rE "fastapi|pydantic|json|uvicorn" app/domain/
```

### Por qué "ligera"

La hexagonal "de libro" trae más ceremonia (DTOs en cada frontera, mappers
bidireccionales, un módulo por puerto). Para una prueba de 4–6h eso sería
sobre-ingeniería. Tomamos solo lo que paga: **dominio puro + puertos +
inyección de dependencias**. Saber *dónde paraste* y *por qué* es justo lo que
evalúan en "decisiones documentadas".

---

## 2. Mapa de archivos (qué hace cada uno)

```
app/
├── domain/                  ← NÚCLEO PURO (reglas)
│   ├── models.py            User, Service, Reservation, enums, solape
│   ├── calendar.py          Horario 07-19, domingos, festivos CO 2026, zona horaria
│   ├── refund_policy.py     Strategy de reembolso (standard/premium/non_refundable)
│   └── exceptions.py        Errores de negocio tipados
│
├── application/             ← ORQUESTACIÓN (casos de uso)
│   ├── ports.py             Interfaces (Protocols): Clock, *Repository
│   └── use_cases.py         CreateReservation, CancelReservation, ListUserReservations
│
├── infrastructure/          ← ADAPTADORES DE SALIDA
│   ├── memory_repo.py       Repos en memoria + SystemClock + lock de concurrencia
│   └── seed_loader.py       Carga tolerante de data/seed.json (datos sucios)
│
└── api/                     ← ADAPTADOR DE ENTRADA (HTTP)
    ├── main.py              build_app: ensambla TODO (inyección de dependencias)
    ├── routes.py            Endpoints delgados
    └── schemas.py           Modelos Pydantic de entrada/salida

data/seed.json               Datos de ejemplo (con inconsistencias intencionales)
tests/                       59 pruebas
```

Orden recomendado de lectura: `domain/models.py` → `domain/calendar.py` →
`domain/refund_policy.py` → `application/ports.py` → `application/use_cases.py`
→ `infrastructure/` → `api/main.py`. De adentro hacia afuera, igual que las
dependencias.

---

## 3. La capa de dominio, archivo por archivo

### 3.1 `domain/models.py` — las entidades

Define los objetos del negocio con `@dataclass`. Tres detalles que debes poder
explicar:

**Enums en vez de strings sueltos.** `Plan` y `ReservationStatus` son enums.
Evita errores de dedo (`"premuim"`) y hace que el código se lea como el
negocio.

```python
class Plan(str, Enum):
    STANDARD = "standard"
    PREMIUM = "premium"
```

(Hereda de `str` para que serialice a JSON directo como texto.)

**`Service` lleva `professional_id`.** El enunciado dice "dos reservas del
mismo profesional no pueden solaparse". El profesional está atado al servicio,
así que la reserva hereda el profesional del servicio al crearse. Decisión de
modelado que debes poder justificar.

**Dos métodos de negocio en `Reservation`:**

```python
def overlaps(self, start, end) -> bool:
    # Intervalos semiabiertos [start, end): tocar bordes NO solapa.
    return self.start < end and start < self.end

def is_active_future(self, now) -> bool:
    # Cuenta para el límite de 3: ni cancelada ni pasada.
    return self.status is ReservationStatus.ACTIVE and self.start > now
```

> **Punto fino de entrevista — la fórmula del solape.** Dos intervalos
> `[a, b)` y `[c, d)` se solapan si y solo si `a < d AND c < b`. Si una cita
> termina justo cuando empieza otra (10:30 y 10:30), **no** se solapan, porque
> usamos intervalos semiabiertos (el final es exclusivo). Esto está probado
> explícitamente en `test_adjacent_reservation_same_professional_is_allowed`.

**¿Por qué `Reservation` no es `frozen=True` pero `User`/`Service` sí?**
Porque la reserva **cambia de estado** (se cancela, se le asigna reembolso).
Usuarios y servicios son inmutables en esta demo.

### 3.2 `domain/calendar.py` — el tiempo y el calendario

Aquí vive la trampa principal del enunciado: **zonas horarias**.

**`BOGOTA = ZoneInfo("America/Bogota")`** — toda comparación se hace en hora de
Bogotá, sin importar en qué zona venga la fecha de entrada.

**`to_bogota(dt)`** — la función de normalización, clave:

```python
def to_bogota(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=BOGOTA)   # naive ⇒ se asume Bogotá
    return dt.astimezone(BOGOTA)           # aware ⇒ se convierte a Bogotá
```

> **Decisión documentada:** una fecha *sin* zona horaria se asume que ya está
> en hora de Bogotá. Una fecha *con* zona (ej. `-03:00` de Argentina) se
> **convierte** a Bogotá antes de validar. Probado en
> `test_start_in_other_timezone_is_normalized_to_bogota`.

**`validate_schedulable(start, end)`** — aplica, en orden: no domingos, no
festivos, no cruzar medianoche, y que **toda la cita** (inicio *y* fin) caiga
entre 07:00 y 19:00.

> **Decisión documentada (ambigüedad del enunciado):** "entre 7:00 y 19:00".
> ¿El fin de la cita puede pasarse de las 19:00? Decidimos que **no**: la cita
> completa debe caber en el horario. Un tinte de 90 min a las 18:30 se rechaza.
> Probado en `test_service_ending_after_closing_is_rejected` y su par a las
> 18:00 exactas que sí pasa.

**Los festivos** son un `frozenset` hardcodeado de 2026 (el enunciado lo
permite). ⚠️ **Tarea para ti:** verifica esa lista contra el calendario
oficial colombiano antes de entregar — es justo el tipo de dato que conviene
revisar a mano. Las festividades trasladables (Ley Emiliani) ya están puestas
en el lunes que se celebran.

### 3.3 `domain/refund_policy.py` — el patrón Strategy

El negocio describe **tres** políticas de reembolso. En vez de un `if/elif`
gigante, cada política es una clase pequeña con el mismo método:

```python
class StandardPolicy:
    def refund_fraction(self, time_until_start):
        if time_until_start > timedelta(hours=24): return FULL   # 100%
        if time_until_start > timedelta(hours=4):  return HALF   # 50%
        return ZERO                                              # 0%

class PremiumPolicy:   # ventanas distintas: 4h y 1h
    ...

class NonRefundablePolicy:
    def refund_fraction(self, _): return ZERO   # siempre 0
```

Y un **selector** que decide cuál usar:

```python
def select_policy(user, service):
    if service.non_refundable:        # ⬅ prioridad máxima
        return _NON_REFUNDABLE
    if user.plan is Plan.PREMIUM:
        return _PREMIUM
    return _STANDARD
```

> **Por qué Strategy y no if/elif:** agregar un cuarto plan (ej. "corporativo")
> es **una clase nueva**, sin tocar el caso de uso de cancelación ni los
> existentes. Es el principio Abierto/Cerrado en acción. Esto es exactamente
> lo que probablemente te pidan en la **modificación en vivo** (ver §8).

> **Decisión documentada — los límites exactos.** "Más de 24 horas" lo leímos
> literal: usamos `>` (estricto). Entonces:
> - Estándar: 24h exactas → 50% (no 100%); 4h exactas → 0%.
> - Premium: 4h exactas → 50%; 1h exacta → 0%.
>
> Es decir, los bordes caen en el tramo **menos generoso**. Está probado valor
> por valor en `test_refunds.py` (tablas parametrizadas).

> **Dinero con `Decimal`, nunca `float`.** `0.1 + 0.2 != 0.3` en float. Para
> plata se usa `Decimal` y se redondea explícito a centavos con
> `ROUND_HALF_UP` en `refund_amount()`.

### 3.4 `domain/exceptions.py` — errores tipados

Una jerarquía de errores de negocio:

```
DomainError
├── NotFoundError      → la capa API la mapea a HTTP 404
│   ├── UserNotFound, ServiceNotFound, ReservationNotFound
└── RuleViolation      → la capa API la mapea a HTTP 409
    ├── ClosedDay, OutsideOperatingHours, InsufficientAdvance,
        OverlappingReservation, ActiveLimitReached, AlreadyCancelled,
        ReservationAlreadyStarted
```

> **Por qué importa:** el dominio lanza errores **semánticos** ("día cerrado"),
> no códigos HTTP. La traducción a 404/409 ocurre **una sola vez** en la API
> (`main.py`). Si mañana expones esto como CLI en vez de HTTP, los errores
> siguen teniendo sentido. Cada error trae un `code` legible (ej.
> `"closed_day"`) que viaja en el JSON de respuesta.

---

## 4. La capa de aplicación

### 4.1 `application/ports.py` — los puertos

Define **interfaces** con `Protocol` (typing estructural de Python). Un
`Protocol` dice "lo que use esto necesita objetos con estos métodos", sin
exigir herencia.

```python
class Clock(Protocol):
    def now(self) -> datetime: ...

class ReservationRepository(Protocol):
    def add(self, reservation): ...
    def get(self, reservation_id): ...
    def save(self, reservation): ...
    def for_user(self, user_id): ...
    def for_professional(self, professional_id): ...
    def atomic(self): ...   # context manager para verificar-y-escribir
```

> **El puerto `Clock` es la joya de la corona para testear.** Todas las reglas
> son **relativas a "ahora"** (2h de anticipación, ventanas de 24/4/1h). Si el
> código llamara a `datetime.now()` directo, las pruebas serían no
> deterministas (pasarían hoy, fallarían mañana). Al inyectar un reloj, en
> producción usamos `SystemClock` y en pruebas un `FakeClock` con una fecha
> fija. **Sin un solo mock de `datetime`.**

> **Por qué `Protocol` y no `ABC` (clase abstracta):** con `Protocol` no hay
> que heredar; cualquier clase con esos métodos "encaja". Menos acoplamiento.

### 4.2 `application/use_cases.py` — la orquestación

Cada caso de uso es una clase que recibe sus dependencias en el constructor
(inyección) y expone `execute()`. **No contienen reglas**: orquestan las
reglas del dominio. Las constantes del negocio viven arriba:

```python
MIN_ADVANCE = timedelta(hours=2)
MAX_ACTIVE_RESERVATIONS = 3
```

**`CreateReservation.execute(user_id, service_id, start)`** hace, en orden:

1. Busca usuario y servicio (404 si no existen).
2. Normaliza `start` a Bogotá y calcula `end = start + duración`.
3. `validate_schedulable(start, end)` → horario/domingo/festivo.
4. Valida anticipación mínima de 2h contra `clock.now()`.
5. **Bajo `atomic()`** (lock): cuenta activas (límite 3) → revisa solape del
   profesional → crea y guarda la reserva.

> **Por qué los pasos 5 van dentro de `atomic()`:** son operaciones de
> **verificar-y-escribir**. Sin el lock, dos peticiones simultáneas podrían
> *ambas* leer "0 solapes" y *ambas* insertar en el mismo cupo. El lock las
> serializa. Ver §6.

**`CancelReservation.execute(reservation_id)`** hace, bajo `atomic()`:

1. Busca la reserva (404), verifica que no esté ya cancelada (409).
2. Verifica que no haya iniciado (`start <= now` → 409).
3. Selecciona política (`select_policy`), calcula fracción y monto.
4. Marca cancelada, guarda `cancelled_at` y `refund_amount`.
5. Devuelve un `CancellationResult` (reserva + política + fracción + monto).

> **Idempotencia / no doble reembolso:** cancelar dos veces lanza
> `AlreadyCancelled` la segunda vez; el reembolso no se recalcula ni se
> duplica. Probado en `test_cancel_twice_is_rejected_and_refund_not_duplicated`.

**`ListUserReservations.execute(user_id, date_from, date_to)`** filtra por
usuario y rango (ambos extremos opcionales) y devuelve **ordenado por fecha**.

---

## 5. La capa de infraestructura

### 5.1 `infrastructure/memory_repo.py`

Implementaciones concretas de los puertos:

- **`SystemClock`** → `datetime.now(tz=BOGOTA)`. La implementación "real" del
  puerto `Clock`.
- **`InMemoryUsers` / `InMemoryServices`** → un `dict` interno.
- **`InMemoryReservations`** → un `dict` + un `threading.RLock`. El método
  `atomic()` es un context manager que toma el lock:

```python
@contextmanager
def atomic(self):
    with self._lock:
        yield
```

> **Por qué en memoria y no una base de datos:** una BD real no demostraría
> más arquitectura en una demo, y sí gastaría tiempo del presupuesto de 4–6h.
> Como los casos de uso dependen del **puerto** (no de esta clase), migrar a
> Postgres es implementar `ReservationRepository` con SQL — sin tocar dominio
> ni casos de uso. Eso es lo que compra la arquitectura.

### 5.2 `infrastructure/seed_loader.py` — datos sucios

El enunciado avisa que el seed trae inconsistencias intencionales. La
estrategia (que debes poder defender) tiene **dos niveles**:

- **Degradar con advertencia** cuando el dato es recuperable: usuario sin
  `plan` → asumir `standard` y registrar un warning.
- **Descartar con reporte** cuando falta algo esencial: reserva sin fecha →
  se omite y se reporta; el arranque **nunca** falla por un registro corrupto.

**`parse_datetime()`** acepta dos formatos: ISO 8601 (con o sin zona) y el
local `DD/MM/YYYY HH:MM`. Cualquier otro invalida solo ese registro.

Las advertencias se acumulan en un `SeedReport` y quedan **visibles en
`GET /health`** — así el operador ve qué se cargó y qué se omitió.

> **Filosofía:** "fail soft" para datos, "fail loud" para bugs. Preferimos
> arrancar con datos parciales + reporte claro a tumbar todo el servicio por
> una fila mala. Probado en `test_seed_loader.py`.

---

## 6. Concurrencia básica (un criterio explícito de evaluación)

El enunciado pide manejar "concurrencia básica". La respuesta honesta:

**En la demo:** las secuencias verificar-y-escribir corren bajo el `RLock` del
repositorio (`atomic()`). La prueba `test_concurrent_booking_same_slot_only_one_wins`
lanza **dos hilos reales** que esperan en una `Barrier` para arrancar al mismo
instante y pelean por el mismo cupo; verifica que **exactamente uno gana** y el
otro recibe `OverlappingReservation`.

**En producción (lo que dirías que harías):** un lock en memoria no sirve si
corres varias réplicas del servicio (cada una con su propia RAM). La solución
real es delegar la garantía a la base de datos: en Postgres, un
**constraint de exclusión** por profesional usando `tstzrange` +
`EXCLUDE USING gist`, dentro de una transacción. Así el no-solape lo garantiza
el motor, no el código de aplicación.

> Saber **dónde** está el límite de tu solución y cuál es el siguiente paso
> correcto vale más que pretender que el lock en memoria es suficiente.

---

## 7. La capa API y el ensamblaje

### `api/main.py` — `build_app()` es el corazón del wiring

Aquí se **inyectan todas las dependencias**. Fíjate en la firma:

```python
def build_app(seed_path=DEFAULT_SEED, clock=None):
    clock = clock or SystemClock()
    users = InMemoryUsers(); services = InMemoryServices(); reservations = InMemoryReservations()
    seed_report = load_seed(seed_path, users, services, reservations)

    app = FastAPI(...)
    app.state.create_reservation = CreateReservation(users, services, reservations, clock)
    app.state.cancel_reservation = CancelReservation(users, services, reservations, clock)
    app.state.list_reservations  = ListUserReservations(users, reservations)
    # + registro del exception_handler que traduce DomainError → HTTP
```

> **Por qué `build_app` recibe `seed_path` y `clock`:** es una *factory*. En
> producción se llama sin argumentos (reloj real, seed por defecto). En las
> pruebas de API (`test_api.py`) se le pasa un `FakeClock` y un seed
> controlado. Misma app, tiempo determinista. Este es el truco que hace
> testeable la capa HTTP.

**El traductor de errores** (registrado una sola vez):

```python
def _status_code(exc):
    if isinstance(exc, NotFoundError): return 404
    if isinstance(exc, RuleViolation): return 409
    return 400
```

### `api/routes.py` — endpoints delgados

Cada ruta hace **una cosa**: leer el request, llamar al caso de uso, devolver
la respuesta. Cero lógica de negocio. Ejemplo:

```python
@router.post("/reservations", status_code=201)
def create_reservation(request, body):
    reservation = request.app.state.create_reservation.execute(
        user_id=body.user_id, service_id=body.service_id, start=body.start)
    return ReservationResponse.from_domain(reservation)
```

### `api/schemas.py` — la frontera Pydantic

Modelos de **entrada** (`CreateReservationRequest`) y **salida**
(`ReservationResponse`, `CancellationResponse`). Pydantic valida tipos en la
frontera y genera la doc OpenAPI. **Importante:** estos modelos son distintos
de las entidades del dominio — el dominio no depende de Pydantic.

---

## 8. Traza completa de un request (memorízala para el walkthrough)

### Crear una reserva — `POST /reservations`

```
1. HTTP llega a routes.create_reservation
2. Pydantic valida el body → CreateReservationRequest (api/schemas.py)
3. Ruta llama app.state.create_reservation.execute(...)   (use_cases.py)
4.   ├─ users.get / services.get          (puerto → InMemory*)
5.   ├─ to_bogota(start), calcula end      (domain/calendar.py)
6.   ├─ validate_schedulable(start, end)   (domain/calendar.py)
7.   ├─ clock.now(), valida 2h             (puerto Clock → SystemClock)
8.   └─ with reservations.atomic():        (puerto → RLock)
9.        ├─ cuenta activas (límite 3)
10.       ├─ revisa solape del profesional
11.       └─ crea Reservation + add()
12. Ruta envuelve en ReservationResponse → JSON 201
   (si algo lanza DomainError → exception_handler → 404/409)
```

### Cancelar — `POST /reservations/{id}/cancel`

```
1. routes.cancel_reservation → use_case.execute(id)
2. with atomic():
3.   ├─ get reserva (404), ¿ya cancelada? (409), ¿ya inició? (409)
4.   ├─ select_policy(user, service)       (domain/refund_policy.py)
5.   ├─ fraction = policy.refund_fraction(start - now)
6.   ├─ amount = refund_amount(price, fraction)   (Decimal, redondeo)
7.   └─ marca cancelada, guarda cancelled_at + refund_amount
8. Devuelve CancellationResponse → JSON 200 con política, fracción y monto
```

---

## 9. Preparación para la "modificación en vivo"

Te pedirán cambiar algo pequeño sobre este código. La arquitectura está hecha
para que esos cambios sean localizados. Practica estos (haz el cambio, corre
`uv run pytest`, revierte):

**Ej. 1 — Nueva política de reembolso (plan corporativo, 100% siempre hasta
30 min antes).** Toca **solo** `domain/refund_policy.py`: agrega
`CorporatePolicy`, añade `CORPORATE` al enum `Plan` en `models.py`, y una
rama en `select_policy`. Cero cambios en casos de uso. *Esto demuestra el
valor del Strategy.*

**Ej. 2 — Cambiar el horario de cierre a las 20:00.** Toca **solo**
`CLOSING = time(20, 0)` en `domain/calendar.py`. Una línea.

**Ej. 3 — Subir el límite de reservas activas a 5.** Toca **solo**
`MAX_ACTIVE_RESERVATIONS = 5` en `use_cases.py`. Una línea.

**Ej. 4 — Agregar un endpoint que liste festivos.** Nueva ruta en
`routes.py` que lea `HOLIDAYS_2026`. No toca dominio.

**Ej. 5 — Permitir reservas los domingos para premium.** Aquí está la
discusión jugosa: la regla de calendario hoy es pura y no conoce al usuario.
Tendrías que pasar el `plan` (o un flag) a `validate_schedulable`, o mover esa
excepción al caso de uso. Buen momento para hablar de *trade-offs*: ¿la regla
pertenece al calendario o a la política de reservas?

> **Estrategia en vivo:** antes de teclear, di en voz alta *qué archivo* vas a
> tocar y *por qué solo ese*. Luego corre las pruebas para demostrar que no
> rompiste nada. Eso comunica que entiendes la arquitectura, no solo el código.

---

## 10. Preguntas probables de entrevista (y respuestas cortas)

**¿Por qué hexagonal y no un CRUD plano?** Porque las reglas son el corazón
del problema; aislarlas las hace testeables sin servidor y protege el negocio
de cambios de framework/BD. Lo mantuve ligero para no sobre-diseñar una demo.

**¿Por qué inyectas el reloj?** Porque todas las reglas dependen del tiempo
relativo; un reloj inyectable las vuelve deterministas en pruebas sin mockear
`datetime`.

**¿Cómo manejas zonas horarias?** Todo se normaliza a `America/Bogota` antes
de validar; naive se asume Bogotá, aware se convierte. Una sola función,
`to_bogota`, es el único punto de verdad.

**¿Qué pasa en los límites exactos de reembolso?** Caen en el tramo menos
generoso (`>` estricto), leyendo "más de 24 horas" literal. Está probado valor
por valor.

**¿Cómo evitas dobles reservas concurrentes?** Lock de verificar-y-escribir en
la demo + prueba de carrera con dos hilos; en producción, constraint de
exclusión en Postgres.

**¿Datos sucios?** Degradar con advertencia si es recuperable, descartar con
reporte si falta lo esencial; nunca tumbar el arranque. Warnings visibles en
`/health`.

**¿Qué dejaste por fuera?** BD real, auth, paginación, festivos más allá de
2026 — documentado en el README con el porqué. El puerto del repo ya está, así
que la BD es el siguiente paso natural.

**¿Qué mejorarías con más tiempo?** Postgres con exclusión por rango,
idempotency keys, eventos de dominio, CI con lint, logging estructurado de
cada decisión de reembolso.

---

## 11. Comandos para experimentar

```bash
cd /Users/pabloandresjg/Documents/Personal/Pruebas/Cuantico/reservas

uv run pytest -v                 # las 59 pruebas
uv run pytest tests/test_refunds.py -v   # solo una suite
uv run uvicorn app.api.main:app --reload # API en :8000, doc en /docs

# Probar a mano:
curl -s localhost:8000/health
curl -s -X POST localhost:8000/reservations -H 'Content-Type: application/json' \
  -d '{"user_id":"u-diana","service_id":"svc-corte","start":"2026-06-18T10:00:00-05:00"}'
```

Lee cada archivo con este tutorial al lado. Cuando puedas explicar **por qué**
cada decisión está donde está (no solo qué hace el código), estás listo para
la entrevista.
