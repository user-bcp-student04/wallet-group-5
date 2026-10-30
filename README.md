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

## Nuevas historias y evidencias

Para cada funcionalidad aprobada, registra su objetivo, alcance, exclusiones,
criterios de aceptación verificables y pruebas previstas. Las historias y
tareas pueden generarse a partir de la propuesta y las especificaciones de
OpenSpec. Para nuevos hallazgos, conserva las secciones existentes de
`HALLAZGOS.md` y añade el componente, un identificador nuevo, evidencia y
estado; no presentes los hallazgos anteriores como si fueran requisitos del
nuevo proyecto. Documenta los contratos y resultados de pruebas conforme se
implementen y verifiquen.
