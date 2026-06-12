# NOTAS — Transparencia sobre uso de IA

Usé **Claude Code** (Anthropic) como asistente durante toda la prueba, de
forma deliberada: el rol es de AI Developer y mi flujo habitual de trabajo
incluye estas herramientas. Lo importante: cada decisión de diseño la tomé
yo, y puedo defender cualquier línea del código.

## Cómo trabajé

1. **Análisis y plan primero, código después.** Le pedí a la IA evaluar el
   enunciado y detectar trampas (zonas horarias, límites exactos de las
   ventanas de reembolso, definición de "reserva activa"). Con eso escribimos
   un plan de ejecución (`PLAN.md`) con las decisiones de arquitectura y los
   supuestos cerrados *antes* de escribir código.
2. **Generación asistida por capas.** El código se generó capa por capa
   (dominio → aplicación → infraestructura → API) siguiendo el plan, no de
   un solo prompt. Revisé cada capa antes de continuar con la siguiente.
3. **Verificación.** Las pruebas cubren los puntos donde una IA (o un humano)
   típicamente se equivoca: límites exactos de las ventanas, bordes de
   intervalos de solape, festivos correctos de 2026.

## Qué hizo la IA

- Primera versión de todas las capas de código, siguiendo el plan acordado.
- La lista de festivos de Colombia 2026 (Ley Emiliani aplicada), que
  **verifiqué manualmente** contra el calendario oficial antes de confiar
  en ella — es exactamente el tipo de dato que una IA puede alucinar.
- El borrador del seed con las inconsistencias intencionales.
- Borradores de README y de estas notas.

## Qué decidí / ajusté yo

- La arquitectura (hexagonal ligera) y el alcance: qué entra en 4–6h y qué
  se documenta como fuera de alcance.
- Los supuestos de negocio (sección "Supuestos" del README): hacia dónde
  caen los límites exactos de reembolso, que la cita completa debe caber en
  el horario, que cancelar no está sujeto al horario de operación.
- La estrategia de datos sucios: degradar con advertencia vs descartar con
  reporte, y exponer las advertencias en `/health`.
- La respuesta a "concurrencia básica": lock de exclusión en el repositorio
  con prueba de carrera real, y la nota honesta de que en producción esto es
  un constraint de base de datos, no un lock en memoria.

## Por qué este flujo

Tratar la IA como un par que escribe rápido pero necesita dirección y
revisión: el plan y los supuestos son míos, la mecanografía es compartida,
y la verificación (pruebas + revisión de cada capa) es la red de seguridad.
Es el mismo criterio que aplicaría integrando IA en un equipo de desarrollo.
