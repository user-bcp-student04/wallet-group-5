# Wallet Group 5

Repositorio de partida para un nuevo proyecto. Conserva la configuración y los
tres componentes heredados del taller anterior:

- `auth/`: autenticación Java 21 con Quarkus y Maven.
- `api/`: API Python 3.13 con FastAPI.
- `web/`: interfaz Angular con Node.js 22.

**Estado:** el alcance de Wallet Group 5 aún está por definir. Los componentes
no están vacíos: mantienen el código, las pruebas y los contratos anteriores
temporalmente. No son un producto listo para producción. La integración entre
el emisor de `auth` y la verificación JWT de `api` está pendiente de comprobar;
arrancar los servicios no garantiza que el inicio de sesión funcione de extremo
a extremo. Consulta `HALLAZGOS.md` antes de reutilizar el código: contiene
riesgos pendientes del proyecto anterior.

## Configuración conservada

Se mantienen Docker Compose, CI, CodeQL, Dependency Review, Dependabot, las
pruebas, los agentes de Copilot y OpenSpec. Las instrucciones de trabajo están
en `AGENTS.md`. Los documentos `HALLAZGOS.md`, `PLAN.md` y los documentos de
`docs/` describen el sistema anterior; son referencias históricas, no requisitos
aprobados para Wallet Group 5. Se conservan mientras exista el código al que
hacen referencia.

La base de datos local `api/data/workshop.db` y los volúmenes de Docker no se
han borrado. No incluyas bases de datos, secretos, tokens ni archivos `.env` en
Git. La configuración actual de Compose conserva el nombre `ai-labs` para no
cambiar accidentalmente los volúmenes existentes.

## Levantar la solución (onboarding de la wallet)

Es el camino más corto para ver el onboarding funcionando. No necesita `auth` ni Docker.

**Requisitos:** Python 3.11–3.13 (recomendado 3.13) y Node.js 22.12+ con npm. Tener acceso a Internet para
llegar al simulador de wallet del grupo 5.

1. **Configura el entorno.** Desde la raíz, copia el archivo de ejemplo (PowerShell:
   `Copy-Item .env.example .env`; Bash: `cp .env.example .env`). Trae `WALLET_MOCK_URL` con la URL del
   simulador del grupo 5 y `ONBOARDING_OTP_TEST_CODE=123456`, el código del doble factor simulado.
   Sin ese código no se puede activar ninguna wallet.
2. **Instala las dependencias (una sola vez).**

   ```bash
   python tools/lab.py setup api
   python tools/lab.py setup web
   ```

   `setup api` exige Python 3.11–3.13 y crea `api/.venv`.
3. **Inicia la API** en una terminal (puerto 8000) y **la web** en otra (puerto 4200). Ambas leen `.env`:

   ```bash
   python tools/lab.py start api
   python tools/lab.py start web
   ```

4. **Comprueba que están arriba.** `http://localhost:8000/docs` debe abrir la documentación de la API.
   Abre `http://localhost:4200/onboarding`.
5. **Recorre el flujo.** Pulsa «Crear o activar mi wallet», ingresa un documento ficticio nuevo, por
   ejemplo `TEST-DEMO-001` (cada documento solo sirve una vez), el código `123456`, confirma el registro y
   verifica que aparece «Wallet activa». «Resultado simulado» permite probar revisión manual,
   rechazo e indisponibilidad del proveedor. Para resolver una revisión manual, aprueba la verificación en el
   simulador con `POST /kyc/verifications/{id}/decision` y `{"decision": "ACTIVE"}` y pulsa «Actualizar estado».

**Con Docker (sin instalar nada más):** `docker compose up --build` levanta `auth`, `api` y `web`; la web
queda en `http://localhost:4200/onboarding`. Compose lee `.env` desde la raíz.

**Problemas frecuentes**

- *El doble factor aparece como no disponible:* falta `ONBOARDING_OTP_TEST_CODE` (6 dígitos) en `.env`, o
  reiniciaste la API sin cargarlo.
- *Error de conexión con el servicio de onboarding:* la API no está iniciada en el puerto 8000.
- *Error al contactar al proveedor (`503`, `504`, `502`):* revisa que `WALLET_MOCK_URL` sea correcta y alcanzable.
  Una variable ya definida en tu entorno prevalece sobre `.env`.
- *Un documento ya usado devuelve un mensaje neutro:* es intencional; usa otro `TEST-…` o borra la cuenta de prueba
  de la base `api/data/workshop.db`.
- Para empezar con una base limpia, detén la API y borra `api/data/workshop.db` (también se pierden las tareas del
  sistema heredado, que se vuelven a crear).

Pruebas automáticas: `python tools/lab.py test api` y `python tools/lab.py test web`.

## Arranque de los servicios heredados

Con Docker y el motor iniciado, desde la raíz:

```bash
docker compose up --build
```

La API requiere las variables de entorno `AUTH_JWT_PUBLIC_KEY`,
`AUTH_JWT_ISSUER` y `AUTH_JWT_AUDIENCE` para validar tokens. Sin esa
configuración, las solicitudes protegidas responden `503`. No guardes claves
privadas ni tokens en el repositorio. La configuración de estas variables no
resuelve por sí sola la integración pendiente con el emisor de `auth`.

La interfaz está en `http://localhost:4200`, la documentación de la API en
`http://localhost:8000/docs` y la comprobación de salud de autenticación en
`http://localhost:8080/q/health`. Para detener los servicios, usa Ctrl+C y:

```bash
docker compose down
```

Este comando conserva los volúmenes. No uses la opción de eliminación de
volúmenes si necesitas conservar sus datos.

### Onboarding de la wallet (simulador)

El recorrido de registro y activación sigue el procedimiento
[docs/stories/onboarding-wallet-procedimiento.md](docs/stories/onboarding-wallet-procedimiento.md)
y usa el simulador de wallet descrito en
[docs/contracts/bcp-wallet-mock-openapi.yaml](docs/contracts/bcp-wallet-mock-openapi.yaml)
(KYC de prueba, sin documentos ni dinero reales). La web habla con la API
(`/api/onboarding`) y la API llama al simulador. Pasos: inicio, documento, doble factor,
persistencia y control de duplicados, activación y salida. Para probarlo:

1. Copia `.env.example` a `.env` (no se versiona). Ahí vive `WALLET_MOCK_URL`, con la URL del
   simulador del grupo 5 (`https://bcp-wallet-mock.yefri.workers.dev/groups/5`). Docker Compose
   lee ese archivo y `python tools/lab.py start api` también; si defines la variable en el
   entorno, prevalece sobre `.env`. Sin ella la API usa `http://127.0.0.1:8787`
   (`compose.yaml`, `http://host.docker.internal:8787`). Ese estado es **compartido por todo el
   grupo**: no uses `POST /control/reset` sin avisar al equipo.
2. Define `ONBOARDING_OTP_TEST_CODE` (6 dígitos) en `.env`. Es el código del **doble factor
   simulado**, un mecanismo de prueba **no aprobado para el MVP**: sin él, el doble factor queda
   no disponible y no se puede activar ninguna wallet. El código nunca se devuelve ni se registra.
3. Inicia la API (`python tools/lab.py start api`, puerto 8000) y, desde `web/`,
   `npm start`. Abre `http://localhost:4200/onboarding` (también hay un enlace en el login).

Variables opcionales: `ONBOARDING_DATA_KEY` (clave Fernet para cifrar el documento; si falta se
crea `api/data/onboarding.key`, fuera de Git) y `ONBOARDING_SUPPORT_MESSAGE` (texto mostrado
cuando el registro no puede continuar).

Endpoints, todos **públicos** salvo el resumen analítico, porque quien se registra aún no
tiene sesión. El identificador aleatorio del onboarding (`onboardingId`) es la única
referencia; el documento y el código nunca van en la URL.

- `POST /api/onboarding` inicia el flujo (evento `onboarding.started`) y devuelve el estado.
- `GET /api/onboarding/{id}` devuelve el estado (`step`, `states.registration|verification|activation|provider`,
  `wallet`, `paymentsEntryAvailable`) y actualiza una revisión pendiente desde el proveedor.
- `PUT /api/onboarding/{id}/document` con `{"documentType": "TEST", "document": "TEST-001", "scenario": "APPROVED"}`
  valida en el servidor, guarda el documento cifrado y emite el desafío (`422` si es inválido; la
  respuesta no repite el valor recibido).
- `POST /api/onboarding/{id}/challenge` reenvía el código (máximo 3 por onboarding).
- `POST /api/onboarding/{id}/two-factor` con `{"code": "123456"}`; `400 TWO_FACTOR_FAILED`
  (`INCORRECT` o `EXPIRED`), `429 TWO_FACTOR_LOCKED` tras 5 fallos en 5 minutos (por onboarding o por
  documento) y `503` si el mecanismo no está disponible.
- `POST /api/onboarding/{id}/activate` exige el doble factor verificado (`403 TWO_FACTOR_REQUIRED`),
  persiste la cuenta y activa la wallet. Una cuenta posiblemente duplicada recibe
  `409 REGISTRATION_UNAVAILABLE` con un mensaje neutro, sin confirmar que exista ni su estado.
  Proveedor: `503`, `504` (resultado incierto), `429` o `502`.
- `POST /api/onboarding/{id}/exit` con `{"action": "CONTINUE" | "END"}` registra la salida; solo con la wallet activa.
- `GET /api/onboarding/analytics/summary` (requiere JWT) devuelve por mes los onboardings iniciados, los
  nuevos usuarios activos y la mediana de duración frente a 180 s. Frontera: de `onboarding.started`
  a `onboarding.closed` con la wallet activa. `cac` es `null` mientras no haya fuente de gasto de adquisición.
  La finalización del onboarding no es el evento de activación de pagos usado para MAU.

Usa documentos ficticios que empiecen con `TEST-`. El selector «Resultado simulado»
solo sirve para pruebas: provoca la aprobación, la revisión manual, el rechazo o la
indisponibilidad del proveedor. Una revisión manual la resuelve un operador con
`POST /kyc/verifications/{id}/decision` en el simulador; la interfaz permite actualizar su estado.

Las cuentas se guardan en `api/data/workshop.db` (tablas `onboarding_sessions`, `onboarding_accounts`
y `onboarding_events`): **un documento de prueba solo puede usarse una vez**. El documento se guarda
cifrado y la unicidad se aplica sobre un derivado con clave. La tabla `accounts` de versiones
anteriores ya no se usa y puede conservar documentos de prueba en texto claro; bórrala si existe.
`POST /control/reset` del simulador borra sus datos pero no esas cuentas.

**Límites y riesgos:** los endpoints de onboarding no tienen autenticación de la persona y
sus límites de intentos son por onboarding y por documento, no por origen; la respuesta
neutra ante una cuenta existente deja una señal residual. Solo son aceptables con documentos
ficticios. El doble factor es una simulación (código de prueba por entorno) y **no está
aprobado para el MVP**. Una revisión pendiente solo se retoma en la misma sesión del navegador.
Siguen fuera de alcance la ejecución de pagos, el evento de activación para MAU y el cálculo de
CAC (no hay fuente de gasto de adquisición). El alcance está en el cambio OpenSpec
`onboarding-wallet-demo`; el borrador `onboarding-wallet` se conserva separado.

## Desarrollo y pruebas

Sin contenedores, instala JDK 21 y Maven 3.9+, Python 3.13 y Node.js 22.12+.
Desde la raíz, prepara y ejecuta cada componente por separado:

```bash
python tools/lab.py setup auth
python tools/lab.py start auth
```

Sustituye `auth` por `api` o `web` para los otros componentes. Para validar:

```bash
python tools/lab.py test auth
python tools/lab.py test api
python tools/lab.py test web
```

`python tools/lab.py test` ejecuta las pruebas de los tres componentes. La API
mantiene un umbral de cobertura global del 85%; la cobertura del código
modificado debe verificarse por separado. Estas pruebas pertenecen a los
contratos heredados, no al alcance aún no definido del nuevo proyecto.

## Crear el alcance nuevo con OpenSpec

OpenSpec ya está configurado; no hace falta reinicializarlo. Define primero la
necesidad, el alcance, las exclusiones y los criterios de aceptación de Wallet
Group 5. Después, desde la raíz:

```bash
openspec new change nombre-del-cambio
openspec status --change nombre-del-cambio
openspec instructions proposal --change nombre-del-cambio
```

Completa los artefactos indicados por `openspec status`, incluyendo propuesta,
diseño, especificaciones y tareas; vuelve a consultar el estado conforme avances.
También puedes pedir a Copilot `/opsx-propose` con la descripción del cambio.
No reutilices la propuesta anterior de JWT como si fuera el alcance del nuevo
proyecto. Revisa y aprueba el alcance antes de implementar o retirar los
contratos heredados.

El repositorio hermano `crewai` ofrece `product_workflow.py` para revisar un
cambio OpenSpec de este producto con sus agentes. Consulta el README de ese
repositorio para seleccionar la ruta del producto, el cambio y los archivos de
contexto. El flujo guarda propuestas en `crewai/output/` y no modifica este
repositorio: revisa y aplica manualmente los cambios, y ejecuta aquí las pruebas.
Una propuesta generada no aprueba decisiones pendientes ni demuestra que las
pruebas hayan sido ejecutadas.

## Nuevas historias y evidencias

Para cada funcionalidad aprobada, registra su objetivo, alcance, exclusiones,
criterios de aceptación verificables y pruebas previstas. Las historias y
tareas pueden generarse a partir de la propuesta y las especificaciones de
OpenSpec. Para nuevos hallazgos, conserva las secciones existentes de
`HALLAZGOS.md` y añade el componente, un identificador nuevo, evidencia y
estado; no presentes los hallazgos anteriores como si fueran requisitos del
nuevo proyecto. Documenta los contratos y resultados de pruebas conforme se
implementen y verifiquen.
