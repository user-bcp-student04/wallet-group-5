# Tasks

## 1. API: cuentas únicas y KYC

- [x] 1.1 Crear la tabla `accounts` con restricción única `(document_type, document)` y su
  repositorio (reservar, completar, liberar, buscar por KYC); verificar duplicados,
  liberación y persistencia con `python -m pytest` desde `api/`.
- [x] 1.2 Implementar el cliente del simulador (crear KYC, consultar KYC y wallet) con
  tiempo de espera y errores tipados; verificar con pruebas sin red.
- [x] 1.3 Implementar el servicio y `POST /api/onboarding` / `GET /api/onboarding/{kycId}`
  con los códigos `201`, `409`, `422`, `404`, `502` y `503`; verificar los tres resultados del KYC, el fallo del proveedor,
  los duplicados, las solicitudes simultáneas y que un fallo del proveedor libera el documento.
- [x] 1.4 Configurar `WALLET_MOCK_URL` en la API y en `compose.yaml`; verificar con
  la prueba de configuración y el análisis sintáctico del YAML (Docker no está instalado
  en este entorno: `docker compose config --quiet` **no se ejecutó**).

## 2. Web: recorrido contra la API

- [x] 2.1 Cambiar el cliente HTTP y la máquina de estados para usar la API, con tipo de
  documento, el error de duplicado y la señal de finalización; verificar con `npm test` en `web/`.
- [x] 2.2 Actualizar la interfaz: tipo y número de documento, mensaje de duplicado y siguiente
  paso de pagos pendiente; comprobar en navegador contra la API real con el simulador.
- [x] 2.3 Retirar el proxy del simulador, ya innecesario; verificar que `npm run build` y
  `npm start` siguen funcionando.

## 3. Documentación y verificación

- [x] 3.1 Documentar la ejecución, los endpoints públicos y sus riesgos en el README; verificar
  que no promete doble factor, pagos ni analítica.
- [x] 3.2 Ejecutar `python tools/lab.py test api` y `npm test`, la cobertura del código nuevo y la
  compilación; registrar los resultados reales y la cobertura frente a la meta de 85 %.
- [x] 3.3 Validar con `openspec validate onboarding-wallet-demo --strict` y confirmar que
  `onboarding-wallet` sigue intacto.
- [x] 3.4 Probar el recorrido contra el simulador real, incluidos códigos de error y cabeceras,
  y registrar el resultado (ver Evidencia: cubre aprobado, duplicado, revisión manual, rechazo,
  no disponible y `404`; **no** se provocaron `429`, `504` ni una wallet no activa).

## 4. Procedimiento de onboarding

Las secciones 1 a 3 cubren el alcance anterior y describen su contrato original (`kycId`,
`409 ACCOUNT_EXISTS`), que esta sección sustituye. Las tareas siguientes cubren los
requisitos añadidos por `docs/stories/onboarding-wallet-procedimiento.md`. Donde dependen de
una decisión de `design.md`, se resolvieron **solo para la simulación** y siguen por aprobar.

- [x] 4.1 API: respuesta neutra `409 REGISTRATION_UNAVAILABLE` sin estado ni identificadores y con el
  texto del canal de asistencia (`ONBOARDING_SUPPORT_MESSAGE`; el texto real sigue por definir); pruebas:
  mismo cuerpo para una cuenta activa, pendiente o rechazada, sin fugas, y solicitudes concurrentes con una sola cuenta.
- [x] 4.2 API: doble factor tras `OtpChannel`, verificado antes de crear o activar la cuenta, con
  límites de intentos y de envíos y rechazo del alta sin segundo factor. **Mecanismo simulado, no aprobado:**
  código de prueba por `ONBOARDING_OTP_TEST_CODE`; sin él no se puede activar ninguna wallet.
- [x] 4.3 API: estados de registro, verificación y activación separados, paso derivado del estado
  persistido, reanudación desde un paso seguro y recuperación de un registro atascado; una solicitud
  incompleta o interrumpida no deja la wallet activa ni registra un cierre.
- [x] 4.4 API: documento cifrado (Fernet) con derivado HMAC para la unicidad; errores de validación sin
  repetir el valor; pruebas de que ni la base, ni los logs ni los eventos contienen el documento o el código.
  Pendiente de un lanzamiento real: gestión de claves y control de acceso a la base.
- [x] 4.5 API: eventos de inicio, finalización de cada paso y cierre, y `GET /api/onboarding/analytics/summary`
  (JWT) con la mediana por mes frente a 180 s. Frontera aplicada: `onboarding.started` →
  `onboarding.closed` con la wallet activa (por confirmar con el Product Owner). El CAC **no se calcula**
  (sin fuente de gasto acordada).
- [x] 4.6 Web: secuencia de cinco pasos con el paso actual, errores junto al campo sin borrar valores válidos,
  conservación de datos al volver, desafío de doble factor, confirmación y salida con el punto de entrada
  a pagos sin iniciar un pago; `npm test` (ver Evidencia).
- [x] 4.7 Web: reanudar tras una interrupción con el estado validado por la API; solo el `onboardingId`
  se guarda en el navegador, nunca el documento ni el código.
- [x] 4.8 README y variable de entorno `WALLET_MOCK_URL` (`.env.example`, `compose.yaml`, `tools/lab.py`);
  validar con `openspec validate onboarding-wallet-demo --strict`; ejecutar las pruebas de `api` y `web`
  (ver Evidencia).

## Evidencia del procedimiento (sección 4)

- `api/`, `python -m pytest --cov=app --cov-fail-under=85`: aprobado, 98,7 % de cobertura total.
- `web/`, `npm test`: 149 pruebas aprobadas (92 de flujo, 54 del cliente HTTP, 2 del almacén,
  1 heredada); `npm run build`: aprobado, con las advertencias existentes de `axios` y `lodash`.
- Contra el **mock real del grupo 5** (`WALLET_MOCK_URL` leída del entorno, base temporal; nunca se
  usó `POST /control/reset`): código incorrecto → `400`; segundo factor → activar → `201`-equivalente `200`
  con wallet `ACTIVE`; salida `CONTINUE` → `200`; el mismo documento en otro onboarding →
  `409 REGISTRATION_UNAVAILABLE` sin llamar de nuevo al mock. Se creó una verificación de prueba
  (`TEST-LIVE-…`) en el estado compartido del grupo.
- **Navegador** (Chromium integrado, API y web levantadas con `python tools/lab.py start api|web`, base
  temporal, mock real del grupo 5): documento inválido bloqueado con el mensaje junto al campo y el valor
  conservado; código mal formado e incorrecto; «Volver al documento» conserva el número y «Cancelar» regresa
  al doble factor; recarga que retoma el paso desde la API; código válido → activación → «Wallet activa» con
  el punto de entrada a pagos que no inicia ningún pago; «Terminar»; mismo documento en otro onboarding →
  mensaje neutro sin revelar la cuenta; revisión manual → «en revisión», recarga la mantiene, el operador
  aprueba en el mock y «Actualizar estado» activa la wallet; rechazo sin entrada a pagos. `sessionStorage`
  solo contiene el `onboardingId`; ni el documento ni el código están en el almacenamiento ni en la base;
  sin desborde horizontal a 375 px; los eventos de analítica quedaron en orden y el duplicado no cerró.
- **No verificado:** el doble factor no disponible en el navegador (solo pruebas automáticas); `429`,
  `504` y wallet no activa contra el mock real (solo pruebas unitarias); `docker compose config`
  (Docker no está instalado).
- Dictamen de Chapter sobre la ejecución previa de los agentes: no aprobar; esta entrega responde a esos
  hallazgos (respuesta sin enumeración, doble factor, estados separados, analítica, protección del documento).

## Evidencia (alcance anterior)

- `api/`, `python -m pytest --cov=app --cov-fail-under=85`: 117 pruebas aprobadas
  (2 `xfail` heredadas), 98,6 % de cobertura total; todo el código nuevo de
  onboarding está cubierto.
- `web/`, `npm test`: 73 pruebas aprobadas. Cobertura del código de onboarding
  (sin el componente Angular): 100 % de líneas y ramas.
- `npm run build` en `web/`: aprobado, con las advertencias existentes de `axios` y `lodash`.
- `openspec validate onboarding-wallet-demo --strict` y `onboarding-wallet --strict`: aprobados.
- Extremo a extremo con la API real, la web y un simulador **sustituto temporal** que sigue el
  contrato (no el real): documento inválido bloqueado; aprobado con wallet confirmada; duplicado
  rechazado con `409`; doble clic con una sola verificación; revisión manual que sobrevive a una
  recarga y pasa a activa tras la decisión del operador; rechazo; `503` que libera el documento
  (la base solo contiene una fila por documento aceptado). A 375 px no hay desborde y el documento no
  queda en el almacenamiento del navegador.
- Contra el **mock real en la nube del grupo 5** (API real con `WALLET_MOCK_URL`, base temporal;
  nunca se usó `POST /control/reset`): `APPROVED` → `201` con wallet `ACTIVE` confirmada y el mismo
  documento → `409` sin llamar de nuevo al mock; `MANUAL_REVIEW` → `PENDING`, la decisión `ACTIVE` del
  operador en el mock y la consulta posterior → `ACTIVE` con wallet; `REJECTED` → `201` sin wallet;
  `UNAVAILABLE` → `503 KYC_UNAVAILABLE` y el mismo documento se pudo reintentar; identificador
  desconocido → `404` sin llamar al mock. En la interfaz (375 px): aprobado en menos de 1 s y duplicado
  con su mensaje. Se crearon unas 5 verificaciones de prueba (`TEST-REAL-…`) en el estado compartido del grupo.
  **No se probaron** contra el mock real `429`, `504`/timeouts ni una wallet no activa (solo con pruebas unitarias).
  Diferencias con el contrato: `GET /health` informa `storage: sqlite` (el contrato dice memoria), los
  identificadores tienen formato `kyc_…`/`wallet_…` y el CORS del mock es abierto (`*`).
- Los seis agentes del Crew se ejecutaron dos veces. La primera, sobre el cambio **antes** de terminar la
  implementación y sin el Issue ni el contrato (dictamen «no aprobar»). La segunda, sobre la solución final
  con la HU (docs/stories/onboarding-wallet.md), el contrato y el código con sus pruebas: Chapter tampoco
  aprobó el cierre. Corregido a raíz de esa revisión: una wallet no activa ya no cuenta como confirmada (API y
  web), una consulta fallida tras recargar ofrece reintentar y bloquea otro registro, un timeout se informa como
  resultado incierto (504) y no como «no se creó ninguna wallet», el límite 429 del proveedor llega a la web,
  y se aclaró en el diseño que status es el resultado del KYC. Sigue sin aprobarse el uso real: endpoints
  públicos, enumeración, documento en texto claro y duplicado posible tras un timeout (ver diseño).

## Pendiente fuera de esta entrega

- Ejecución de pagos, cobros QR y el evento de activación para MAU (historia de confirmación de pagos).
- Autenticación de la persona, KYC y documentos reales y requisitos regulatorios para un lanzamiento real.

La evidencia anterior corresponde al alcance previo a `docs/stories/onboarding-wallet-procedimiento.md`;
no demuestra los requisitos de la sección 4.
