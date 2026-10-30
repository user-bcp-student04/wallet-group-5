# Procedimiento de onboarding de la wallet

Complementa la historia [Onboarding de la wallet](onboarding-wallet.md). Si ambas difieren,
prevalece este procedimiento, que es la versión más reciente.

## 1. Objetivo

Guiar a una persona usuaria de smartphone desde el inicio del registro hasta una wallet activa, con pasos visibles, validaciones comprensibles y autenticación de doble factor. El procedimiento busca reducir fricción y alcanzar una mediana de finalización de 3 minutos para la cohorte MVP en Perú, sin debilitar la seguridad.

## 2. Alcance

Este procedimiento cubre exclusivamente el onboarding: inicio, captura y validación de los datos mínimos de documento, doble factor, prevención de cuentas duplicadas, activación de la wallet, instrumentación y salida del flujo.

Al finalizar, se habilita el punto de entrada a pagos de bajo monto. La ejecución de pagos, los cobros QR y su operación quedan fuera de este procedimiento.

## 3. Reglas de experiencia

- Mostrar desde el inicio la secuencia de pasos y destacar el paso actual durante todo el flujo.
- Usar lenguaje breve, cotidiano y accionable; indicar qué dato corregir y cómo continuar.
- Solicitar como requisitos de documento únicamente el tipo y el número, conforme al supuesto de la historia.
- Evitar pedir nuevamente datos ya capturados si la persona vuelve a un paso anterior.
- No avanzar cuando falte un dato obligatorio, sea inválido o no se haya completado el doble factor.
- Diseñar el recorrido para que la mediana no supere 3 minutos; la medición se realiza para la cohorte MVP durante el trimestre posterior al lanzamiento.

## 4. Secuencia del procedimiento

| Paso | Acción de la persona usuaria | Comportamiento del sistema | Resultado |
|---|---|---|---|
| 1. Inicio | Selecciona crear o activar su wallet y revisa qué necesitará para completar el registro. | Inicia el flujo y registra el evento de inicio con su marca de tiempo. Presenta la secuencia de pasos y señala el primero. | La persona sabe qué esperar y cómo avanzar. |
| 2. Datos de documento | Selecciona el tipo de documento e ingresa su número. | Mantiene visible el progreso. Valida que ambos campos estén presentes y que el valor tenga un formato admisible para el tipo seleccionado. | Los datos mínimos quedan listos para verificación. |
| 3. Corrección, si aplica | Corrige los campos señalados. | Bloquea el avance si falta información o hay datos inválidos. Explica el error junto al campo y da una instrucción concreta, sin borrar los valores válidos. | Solo se permite continuar con datos completos y válidos. |
| 4. Doble factor | Completa el desafío de autenticación presentado por el sistema. | Verifica el segundo factor antes de crear o activar la cuenta. Informa de forma clara si la verificación no se completó y permite volver a intentarlo de manera segura. | La identidad de acceso queda confirmada según el mecanismo aprobado para el MVP. |
| 5. Persistencia y control de duplicados | Continúa después de validar sus datos y el doble factor. | Persiste la cuenta de forma consistente y evita crear otra cuenta para el mismo usuario. Si detecta una cuenta existente, no crea una duplicada y presenta una orientación segura para continuar por el canal definido. | Existe una sola cuenta persistida por usuario. |
| 6. Activación | Confirma la finalización del registro. | Cambia el estado de la wallet a activo solo cuando los pasos requeridos finalizaron correctamente. Registra el cierre del flujo y muestra una confirmación sencilla. | La wallet queda activa. |
| 7. Salida | Selecciona continuar o termina la sesión. | Muestra el punto de entrada a pagos de bajo monto y registra la finalización de los pasos y el cierre del flujo para analítica. No inicia un pago como parte del onboarding. | La persona conoce el siguiente paso sin salir del alcance de onboarding. |

## 5. Manejo de excepciones

- **Dato faltante o inválido:** mantener a la persona en el paso actual, señalar el campo y explicar la corrección necesaria.
- **Doble factor no completado:** no activar la wallet. Mostrar el estado y la acción disponible sin revelar secretos ni detalles internos de validación.
- **Cuenta posiblemente duplicada:** no crear otra cuenta. Evitar mensajes que expongan información de una cuenta a terceros; orientar a la persona hacia el canal de acceso o asistencia definido para el MVP.
- **Interrupción antes de completar:** no marcar la wallet como activa. Al retomar, validar el estado persistido y continuar desde un paso seguro, sin registrar una finalización ficticia.
- **Falla técnica:** informar que no se pudo completar el paso y ofrecer reintentar o salir; no presentar el onboarding como exitoso si la persistencia o activación falló.

## 6. Consideraciones técnicas

- Mantener una fuente consistente del paso actual y del estado del onboarding para que la interfaz y el backend no indiquen resultados contradictorios.
- Validar los datos en el servidor además de la validación de interfaz. La interfaz ayuda a corregir; no sustituye la validación del sistema.
- Persistir la cuenta y prevenir duplicados con una operación consistente ante solicitudes repetidas o concurrentes.
- Activar la wallet únicamente después de completar las validaciones requeridas; el acceso a pagos depende de ese estado activo.
- Instrumentar como mínimo el inicio, la finalización de cada paso y el cierre, incluyendo marcas de tiempo suficientes para medir duración.
- Acordar la frontera analítica oficial de inicio y fin antes de reportar la mediana. La historia deja esta definición como pregunta abierta.
- Separar la finalización del onboarding de la activación usada para MAU: el reporte mensual debe considerar el evento de activación emitido por pagos exitosos definido en la historia de confirmación de pagos.
- La salida analítica debe permitir revisar nuevos usuarios activos por mes y la atribución de gasto necesaria para evaluar MAU de 1,000 a 2,000 y CAC de PEN 10 durante los primeros tres meses. El origen y las reglas de atribución del gasto requieren coordinación con sus responsables.
- No asumir un único riel de pago ni agregar integraciones de proveedores al onboarding si no son necesarias para los requisitos definidos.

## 7. Consideraciones de seguridad

- Transmitir los datos de documento y los datos de autenticación mediante canales cifrados; proteger los datos persistidos con controles de acceso y cifrado adecuados.
- Aplicar minimización de datos: recolectar solo el tipo y número de documento requeridos por esta historia. No incluir esos valores, códigos de verificación, secretos o credenciales en logs, analítica ni mensajes de error.
- Restringir el acceso a datos personales a los componentes y personas autorizadas para operar el onboarding.
- Proteger el doble factor frente a intentos automatizados y abuso, mediante límites y controles de frecuencia; no revelar códigos ni detalles que permitan eludir la verificación.
- Evitar enumeración de cuentas: las respuestas ante posibles duplicados no deben confirmar a una persona no autenticada si existe una cuenta asociada a un documento.
- Registrar eventos de analítica con identificadores técnicos no sensibles y datos mínimos; no usar el número de documento como identificador de eventos.
- Mantener separados los estados de registro, verificación y activación para impedir que una falla o una solicitud incompleta deje una wallet activa por error.

## 8. Seguimiento y criterios de salida

El onboarding se considera completado únicamente cuando:

1. Los pasos requeridos y el paso actual se mostraron durante el flujo.
2. Los datos obligatorios fueron validados y el doble factor fue completado.
3. La cuenta quedó persistida sin duplicar una cuenta existente.
4. La wallet cambió a estado activo y el punto de entrada a pagos de bajo monto quedó disponible.
5. Se registraron el inicio, las finalizaciones de pasos y el cierre para analítica.

Para seguimiento del MVP, revisar la mediana de duración frente al objetivo de 3 minutos, los conteos mensuales de nuevos usuarios activos, MAU y CAC en los meses 1 a 3. Los umbrales de MAU (1,000–2,000) y CAC (PEN 10) son objetivos definidos por el Product Owner, no decisiones de este procedimiento.
