# Design

## Context

La HU pide un onboarding guiado que active la wallet, abra pagos de bajo monto y
alimente métricas. Sus supuestos añaden: solo tipo y número de documento, duración
máxima de 3 minutos, finalización como disparador de los pagos, doble factor y
cuentas únicas persistidas. El procedimiento
(`docs/stories/onboarding-wallet-procedimiento.md`) lo amplía: siete pasos, doble
factor verificado antes de crear o activar la cuenta, respuesta sin enumeración ante
duplicados, punto de entrada a pagos al salir, instrumentación y requisitos de
seguridad. La entrega sigue siendo una simulación. El simulador de
wallet (`docs/contracts/bcp-wallet-mock-openapi.yaml`, 0.3.0) es un mock sin
autenticación, cuyo KYC solo admite `documentType: TEST`, no evita altas repetidas y
no ofrece API de segundo factor.

## Goals / Non-Goals

**Goals:** recorrido móvil y accesible, validación en web y API, cuenta única
persistida sin enumeración, doble factor antes de la cuenta, resultado claro para los
tres resultados del KYC y el fallo del proveedor, estado de wallet confirmado, punto
de entrada a pagos de bajo monto e instrumentación con datos mínimos.

**Non-Goals:** ejecución de pagos y cobros QR, el evento de activación para MAU
(lo emiten los pagos), el cálculo de CAC sin fuente de gasto acordada, KYC real, resolución de
revisiones por el operador, autenticación de la persona usuaria y cambios en el
sistema heredado.

## Decisions

- **La API orquesta el KYC.** `api/` recibe el onboarding, comprueba la cuenta única
  y llama al simulador. El simulador no evita duplicados, así que la regla solo
  puede aplicarse en un lugar propio y atómico; además la web deja de depender del
  CORS y del proxy del simulador. La URL del simulador sale de la variable de entorno
  `WALLET_MOCK_URL` (por defecto `http://127.0.0.1:8787`); nunca de la entrada de la
  persona. El repositorio la declara en `.env.example` (URL del grupo 5), que Compose y
  `tools/lab.py` leen desde `.env`, sin versionar el `.env` real.
- **Contrato de la API.** Todos los endpoints son **públicos** (quien se registra aún
  no tiene sesión y `auth/` emite tokens incompatibles con el verificador de la API)
  salvo el resumen analítico. El identificador aleatorio `onboardingId` es la única
  referencia; el documento y el código nunca van en la URL. Los contratos heredados no cambian.
  - `POST /api/onboarding` inicia el flujo: `201` con el estado.
  - `GET /api/onboarding/{id}` devuelve el estado y refresca una revisión pendiente
    desde el proveedor; `404 NOT_FOUND`; `503`/`502`/`504`/`429` del proveedor sin
    modificar el estado.
  - `PUT /api/onboarding/{id}/document` con `{documentType: "TEST", document, scenario}`
    (`scenario` ∈ `APPROVED`, `MANUAL_REVIEW`, `REJECTED`, `UNAVAILABLE`; solo para
    pruebas) valida, guarda el documento cifrado y emite el desafío. `422` sin repetir el
    valor recibido; `409 INVALID_STEP` si el segundo factor ya se verificó.
  - `POST /api/onboarding/{id}/challenge` reenvía el código (máximo 3 por onboarding).
  - `POST /api/onboarding/{id}/two-factor` con `{code}` de 6 dígitos: `400
    TWO_FACTOR_FAILED` (`INCORRECT` | `EXPIRED`), `429 TWO_FACTOR_LOCKED` (con
    `Retry-After`), `429 TWO_FACTOR_LIMIT`, `503 TWO_FACTOR_UNAVAILABLE`.
  - `POST /api/onboarding/{id}/activate`: `403 TWO_FACTOR_REQUIRED` sin segundo factor
    verificado; `409 REGISTRATION_UNAVAILABLE` con un mensaje neutro ante una cuenta
    posiblemente duplicada; `503 KYC_UNAVAILABLE` (no creó nada), `504 KYC_RESULT_UNKNOWN`
    (la llamada falló o agotó el tiempo; el proveedor pudo procesarla), `429
    PROVIDER_LIMIT_REACHED`, `502 PROVIDER_ERROR`.
  - `POST /api/onboarding/{id}/exit` con `{action: "CONTINUE" | "END"}`: solo con la
    wallet activa (`409 INVALID_STEP` si no).
  - `GET /api/onboarding/analytics/summary` exige JWT (datos de seguimiento, no de la persona).
  - El estado devuelto es `{onboardingId, step, states: {registration, verification,
    activation, provider}, twoFactorAvailable, wallet|null, paymentsEntryAvailable}`.
- **Estados separados y fuente única.** La sesión guarda por separado el **registro**
  (`STARTED`, `DOCUMENT_VALID`, `PERSISTING`, `PERSISTED`), la **verificación** del segundo
  factor (`PENDING`, `CHALLENGED`, `VERIFIED`) y la **activación** (`INACTIVE`, `PENDING`,
  `REJECTED`, `ACTIVE`), además del resultado del KYC (`provider`). La activación solo pasa a
  `ACTIVE` con documento válido, segundo factor verificado, cuenta persistida y wallet
  confirmada. El `step` se **deriva siempre del estado persistido** (nunca va por delante de lo
  completado) y la interfaz lo muestra tal cual, de modo que web y API no se contradicen.
- **Doble factor (simulación, mecanismo no aprobado).** Se verifica en la API **antes** de
  persistir o activar la cuenta; `activate` rechaza una solicitud sin segundo factor
  verificado. La API lo aísla tras un canal de desafío (`OtpChannel`). Como el
  procedimiento limita los datos a tipo y número de documento y el simulador no tiene
  API de segundo factor, la simulación usa un **código de prueba de 6 dígitos tomado de
  `ONBOARDING_OTP_TEST_CODE`** (sin dato de contacto adicional). Sin esa variable el doble factor
  no está disponible: no se puede verificar ni activar y la interfaz no lo presenta como
  cumplido. El código vence en 5 minutos, solo se guarda un derivado con clave, nunca se
  devuelve ni se registra. Un lanzamiento real requiere un mecanismo aprobado (canal y
  destino) y sustituir ese canal.
- **Límites de intentos.** 5 fallos en 5 minutos bloquean la verificación (cuenta el
  mayor entre los fallos del onboarding y los de todos los onboardings del mismo documento) y
  como máximo 3 códigos por onboarding. Son valores iniciales de la simulación, por validar.
- **Cuenta única sin enumeración.** `onboarding_accounts` tiene restricción única sobre
  `(document_type, document_hash)`; el valor es un HMAC con clave del documento. La cuenta
  se reserva en `activate`, después del segundo factor, con una transición atómica
  del registro (`DOCUMENT_VALID` → `PERSISTING`) que hace idempotentes los reintentos del mismo
  onboarding. Si la restricción falla, la API responde `409 REGISTRATION_UNAVAILABLE` con el
  mismo cuerpo para cualquier cuenta existente (en cualquier estado) o reserva concurrente, sin
  estado ni identificadores, y orienta al canal definido en `ONBOARDING_SUPPORT_MESSAGE`. Si el
  proveedor falla, la reserva se libera. Un registro atascado en `PERSISTING` más de 30 s se
  recupera al consultarlo y libera la reserva. Las escrituras se serializan con un candado
  compartido porque la conexión SQLite se comparte entre hilos.
- **Protección de datos.** El documento se guarda cifrado (Fernet) con la clave de
  `ONBOARDING_DATA_KEY`, o una clave local creada en la carpeta de datos (fuera de Git). Los
  errores de validación del onboarding no repiten el valor recibido. El documento solo viaja
  en claro al simulador, que lo necesita para el KYC de prueba.
- **Revisión manual y reanudación.** `POST /kyc/verifications/{id}/decision` es del
  operador y no se expone. La persona consulta con `GET /api/onboarding/{id}`. La web guarda
  solo el `onboardingId` en `sessionStorage` y al recargar recupera el estado desde la API
  (paso seguro, sin pedir de nuevo el documento validado). Mientras hay una revisión pendiente
  (o una aprobación sin confirmar) la interfaz no ofrece empezar de nuevo.
- **Salida y finalización.** Con la wallet activa confirmada se muestra el punto de entrada a
  pagos de bajo monto (`paymentsEntryAvailable`); la web notifica `onCompleted` una vez por
  onboarding. No hay navegación a pagos ni se inicia un pago.
- **Analítica.** La API registra en `onboarding_events` el inicio (`onboarding.started`), la
  finalización de cada paso (`DOCUMENT`, `TWO_FACTOR`, `PERSISTENCE`, `ACTIVATION`, `EXIT`) y el
  cierre (`onboarding.closed`, emitido al confirmarse la wallet activa), cada uno una sola vez, con
  marca de tiempo UTC y el `onboardingId`; nunca el documento ni el código. **Frontera acordada:**
  inicio = `onboarding.started`; fin = `onboarding.closed` con la wallet activa. El resumen
  agrega por mes los iniciados, los nuevos usuarios activos y la mediana frente a 180 s. El
  CAC no se calcula: no hay fuente ni reglas de atribución del gasto y la salida lo declara
  (`SOURCE_PENDING`). La finalización del onboarding es distinta del evento de activación de
  pagos que usa MAU.
- **Duración.** Objetivo de diseño de una mediana de 3 minutos: pocos pasos, un único
  envío por paso y esperas acotadas (15 s en la web, 5 s hacia el simulador). No hay
  temporizador en la interfaz.
- **Capas.** API: rutas → servicio → repositorios, cliente del proveedor, canal OTP y
  protección de datos (inyectables). Web: cliente HTTP → máquina de estados → componente.
  Ambas pruebas se ejecutan sin red.
- **Repintado explícito.** La web no declara detección de cambios con zone.js y
  Angular 21 trabaja sin zona por defecto, así que el componente marca la vista
  para revisión tras cada operación asíncrona.

## Risks / Trade-offs

- **Endpoints públicos:** el onboarding no tiene sesión. Los límites de intentos son por
  onboarding y por documento; no hay límite por origen, así que quien cree sesiones
  nuevas con documentos distintos puede seguir adivinando el código de prueba. La respuesta
  neutra tampoco elimina la señal residual (distinta del éxito) tras el segundo factor.
  Aceptable solo con documentos ficticios; un lanzamiento real exige un mecanismo de
  segundo factor aprobado, límites por origen y una política de enumeración revisada.
- **Doble factor simulado:** un código de prueba fijo no autentica a nadie. Casi todo mecanismo
  real necesita un destino (teléfono, correo o dispositivo); si requiere un dato adicional,
  contradice la regla de recolectar solo tipo y número de documento.
- **Tabla heredada `accounts`:** versiones anteriores guardaron documentos de prueba en
  texto claro; la tabla ya no se usa y no se migra ni se borra automáticamente.
- **Tiempo de espera ambiguo:** si la llamada al proveedor falla o tarda más de 5 s pero
  este llegó a crear la verificación, la API responde `504` (resultado incierto), libera
  el documento y la interfaz no afirma que no se creó nada; un reintento podría duplicar
  la verificación en el proveedor. El simulador no permite buscar por documento, así que
  no hay forma de reconciliar; es un riesgo residual de la simulación.
- **Locks parciales:** el candado del onboarding no cubre las escrituras de tareas,
  que comparten la misma conexión SQLite (código heredado, sin modificar).
- **Revisión pendiente atrapada:** como el documento queda bloqueado y el identificador
  solo vive en `sessionStorage`, cerrar la pestaña impide retomar la revisión hasta
  que un operador la resuelva. Un lanzamiento real necesita sesión de la persona
  usuaria para recuperarla.
- La base `api/data/workshop.db` es compartida y persistente: un documento de
  prueba solo sirve una vez.
- El simulador es único por grupo: un `POST /control/reset` borra sus verificaciones
  pero no las cuentas de la API; esas cuentas quedarían sin verificación (la
  consulta devolvería `502`).

## Open Questions

- ¿Qué mecanismo de doble factor se aprueba para el MVP, por qué canal y con qué dato? (la
  simulación usa un código de prueba por entorno).
- ¿Quién es responsable del gasto de adquisición y cuáles son sus reglas de atribución
  (CAC de PEN 10)? ¿Cómo se alinea la analítica con el evento de activación de pagos
  usado para MAU (1,000–2,000)?
- ¿Cuál es el texto y el canal reales de acceso o asistencia para una cuenta existente?
  (hoy es un texto configurable).
- ¿Son adecuados los límites de intentos y la retención de la analítica?
- Resueltas para la simulación, por confirmar con el Product Owner: la frontera analítica
  (`onboarding.started` → `onboarding.closed` con wallet activa).

## Migration Plan

Se agregan las tablas `onboarding_sessions`, `onboarding_accounts` y `onboarding_events` con
`CREATE TABLE IF NOT EXISTS`; no modifican `tasks`. Para deshabilitar el flujo se retiran el
router y la ruta web. Borrar cuentas de prueba es una operación manual sobre
`onboarding_accounts` (y su sesión); no hay endpoint de borrado.
