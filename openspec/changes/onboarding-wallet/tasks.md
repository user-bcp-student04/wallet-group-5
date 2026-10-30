# Tasks

## 1. Decisiones y caracterización previas

- [ ] 1.1 Obtener y registrar aprobación humana de proveedor de correo, política de contraseña, duración y longitud de código, límites, reenvío, contratos HTTP, destino y transporte de sesión; verificar que no quedan decisiones bloqueantes del diseño sin resolver.
- [ ] 1.2 Acordar protección y rotación de claves, almacenamiento, despliegue y acceso de la sesión a servicios heredados; verificar revisión de seguridad documentada.
- [ ] 1.3 Agregar pruebas de caracterización de `POST /auth/login`, persistencia y token antes de modificarlos; ejecutar las pruebas de `auth` y registrar resultado real.
- [ ] 1.4 Caracterizar los contratos relevantes de `/api/tasks` y el flujo web heredado; ejecutar las pruebas afectadas y registrar cualquier fallo previo sin modificar sus expectativas.

## 2. Cuenta y verificación en auth

- [ ] 2.1 Añadir almacenamiento y migración versionada para cuenta pendiente y activa sin modificar datos heredados; probar unicidad, aislamiento y rollback.
- [ ] 2.2 Implementar validación y hash seguro de contraseñas según política aprobada; probar campos inválidos, ausencia de texto plano y no exposición en respuestas y logs.
- [ ] 2.3 Implementar registro con respuesta equivalente para correos nuevos y existentes; probar que cuentas activas y sus sesiones no cambian.
- [ ] 2.4 Implementar desafíos seguros, reemplazo de registros pendientes y consumo atómico; probar vencimiento, reutilización, límites, vinculación y solicitudes concurrentes.
- [ ] 2.5 Implementar adaptador de correo aprobado y adaptador de pruebas aislado; probar entrega, fallos y respuestas públicas equivalentes sin revelar códigos.
- [ ] 2.6 Documentar contratos nuevos, configuración y recuperación del envío; verificar que la documentación coincide con las pruebas y no contiene secretos.

## 3. Sesión e interoperabilidad

- [ ] 3.1 Emitir una sesión JWT RS256 tras verificación exitosa usando claves configuradas externamente; probar que una cuenta pendiente, un código incorrecto y una configuración ausente no obtienen sesión.
- [ ] 3.2 Validar con claves de prueba que la API acepta la sesión nueva y rechaza firma, audiencia, emisor y expiración inválidos; conservar los contratos existentes de tareas.
- [ ] 3.3 Documentar configuración de claves, claims y política de sesión acordada; verificar que no se incluyen valores reales ni instrucciones que alteren datos heredados.

## 4. Registro en web

- [ ] 4.1 Crear formulario de registro y servicio HTTP tipado con validaciones aprobadas; probar entrada válida e inválida y respuestas genéricas sin cambiar el login heredado.
- [ ] 4.2 Crear pantalla de código y gestionar error, expiración y límite de intentos; probar que no existe sesión antes de una verificación exitosa.
- [ ] 4.3 Implementar sesión y navegación al destino aprobado tras verificación; probar el éxito y los fallos sin redirigir al dashboard heredado como wallet.
- [ ] 4.4 Documentar el flujo y configuración de la interfaz; ejecutar pruebas y compilación web, verificando los estados visibles y contratos.

## 5. Integración y revisión

- [ ] 5.1 Ejecutar un flujo completo con proveedor y claves de prueba: registro, correo, código, sesión y verificación JWT; comprobar que no se crea una wallet operativa.
- [ ] 5.2 Ejecutar regresión de `auth`, `api` y `web` con los comandos del repositorio; registrar resultados reales, cobertura del código modificado frente a la meta del 85% y fallos preexistentes.
- [ ] 5.3 Revisar enumeración, abuso, concurrencia, dependencias y exposición de datos; registrar riesgos residuales y evidencia de revisión humana antes de habilitar el flujo.
