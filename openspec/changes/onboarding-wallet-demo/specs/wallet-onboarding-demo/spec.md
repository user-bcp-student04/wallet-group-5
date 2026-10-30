# Wallet onboarding demo

## ADDED Requirements

### Requirement: Recorrido guiado con paso actual visible
El sistema SHALL mostrar desde el inicio la secuencia completa de pasos (inicio,
documento, doble factor, activación y salida) e identificar el paso actual en todo
momento, con lenguaje breve y accionable. SHALL mantener una única fuente del paso y
del estado del onboarding en la API, de modo que la interfaz no indique un resultado
distinto del que registró el servidor.

#### Scenario: Inicio del recorrido
- **WHEN** la persona elige crear o activar su wallet
- **THEN** ve qué necesitará, la secuencia completa y el primer paso como actual, y se registra el evento de inicio

#### Scenario: Avance y retroceso
- **WHEN** la persona avanza o vuelve a un paso anterior
- **THEN** el indicador refleja el paso mostrado y los datos ya capturados no se vuelven a pedir

#### Scenario: Interfaz y servidor coinciden
- **WHEN** la interfaz muestra el estado del onboarding
- **THEN** ese estado proviene de la respuesta de la API y no de una suposición local

### Requirement: Tipo y número de documento como único requisito de identidad
El sistema SHALL solicitar únicamente el tipo y el número de documento, SHALL
aceptar el tipo `TEST` y un número que empiece con `TEST-` seguido de un código
de hasta 200 caracteres en total, y SHALL bloquear el avance con un mensaje junto al
campo que indique cómo corregirlo si el dato falta o es inválido, sin borrar los
valores válidos. La API SHALL aplicar la misma validación en el servidor.

#### Scenario: Número inválido en la interfaz
- **WHEN** la persona intenta continuar con un número vacío, sin el prefijo, solo con el prefijo o demasiado largo
- **THEN** permanece en el paso de documento y recibe junto al campo un mensaje que explica el formato esperado

#### Scenario: Corrección parcial
- **WHEN** un campo es inválido y el otro es válido
- **THEN** solo se señala el campo inválido y el valor válido se conserva

#### Scenario: Solicitud inválida a la API
- **WHEN** la API recibe un tipo distinto de `TEST` o un número que no cumple el formato
- **THEN** responde con un error de validación y no crea ninguna cuenta

### Requirement: Doble factor antes de crear o activar la cuenta
El sistema SHALL presentar un desafío de doble factor y SHALL verificar el segundo
factor en la API antes de crear o activar la cuenta, usando únicamente el mecanismo
aprobado para el MVP. SHALL NOT avanzar ni activar la wallet mientras el desafío no se
haya completado, SHALL informar con claridad que no se completó y permitir reintentar, y
SHALL limitar la frecuencia de los intentos sin revelar códigos ni detalles que permitan
eludir la verificación.

#### Scenario: Desafío completado
- **WHEN** la persona completa el desafío con datos de documento válidos
- **THEN** el segundo factor queda verificado en el servidor y el flujo puede continuar a la persistencia

#### Scenario: Desafío no completado
- **WHEN** el segundo factor es incorrecto, vence o no se completa
- **THEN** no se crea ni se activa ninguna cuenta, se informa el estado y la acción disponible y se permite reintentar

#### Scenario: Intentos en exceso
- **WHEN** se superan los intentos permitidos en el período definido
- **THEN** se bloquean temporalmente nuevos intentos con un mensaje que no revela el código esperado ni cómo eludir el control

#### Scenario: Solicitud que omite el desafío
- **WHEN** la API recibe una solicitud de alta sin segundo factor verificado
- **THEN** la rechaza y no crea ni activa la cuenta

#### Scenario: Mecanismo no aprobado
- **WHEN** el mecanismo de doble factor del MVP no está aprobado
- **THEN** la interfaz no declara que la autenticación sea de doble factor ni permite activar la wallet

### Requirement: Cuenta única persistida y respuesta sin enumeración
El sistema SHALL persistir cada cuenta de onboarding con una operación consistente ante
solicitudes repetidas o concurrentes y SHALL NOT crear una segunda cuenta ni llamar de
nuevo al proveedor para el mismo tipo y número de documento. Ante una cuenta posiblemente
duplicada, SHALL responder de forma neutra, sin confirmar a una persona no autenticada que
exista una cuenta ni exponer su estado o identificadores, y SHALL orientarla al canal de
acceso o asistencia definido para el MVP.

#### Scenario: Documento ya registrado
- **WHEN** se solicita el onboarding de un documento que ya tiene una cuenta en cualquier estado
- **THEN** no se crea otra cuenta y la respuesta es neutra, sin estado ni datos de la cuenta existente, y orienta al canal definido

#### Scenario: Mismo mensaje para otros casos no continuables
- **WHEN** el registro no puede continuar por una cuenta existente o por otra causa no atribuible a la persona
- **THEN** el mensaje no permite distinguir si el documento tiene una cuenta

#### Scenario: Solicitudes simultáneas
- **WHEN** llegan varias solicitudes a la vez para el mismo documento
- **THEN** solo una crea la cuenta y las demás reciben la respuesta neutra

#### Scenario: Persistencia entre reinicios
- **WHEN** la API se reinicia
- **THEN** las cuentas creadas siguen existiendo y siguen impidiendo duplicados

#### Scenario: Fallo del proveedor
- **WHEN** el proveedor no está disponible o la solicitud no se puede completar
- **THEN** no queda ninguna cuenta reservada y la persona puede reintentar con el mismo documento

### Requirement: Verificación con el proveedor simulado desde la API
El sistema SHALL crear la verificación llamando al KYC del simulador desde la API
con `documentType` `TEST`, el número validado y el resultado simulado elegido, solo
después de verificar el doble factor, SHALL NOT añadir otras integraciones de
proveedores ni asumir un único riel de pago, y SHALL impedir envíos duplicados desde la
interfaz mientras haya una solicitud en curso.

#### Scenario: Confirmación del registro
- **WHEN** la persona confirma el registro con el segundo factor verificado
- **THEN** se envía una sola solicitud al onboarding y se indica que la verificación está en curso

#### Scenario: Doble confirmación
- **WHEN** la persona confirma varias veces antes de recibir la respuesta
- **THEN** solo se envía una solicitud

### Requirement: Estados separados y activación solo con pasos completos
El sistema SHALL guardar por separado los estados de registro, verificación y
activación, y SHALL cambiar la wallet a activa únicamente cuando el documento fue
validado, el doble factor verificado, la cuenta persistida y la wallet confirmada con
el proveedor. SHALL mostrar la wallet con su identificador, estado y saldo disponible y
una confirmación sencilla, y SHALL registrar el cierre del flujo.

#### Scenario: Pasos completos
- **WHEN** todos los pasos requeridos terminaron y el proveedor aprueba la verificación
- **THEN** la cuenta queda activa, se muestra la wallet activa confirmada y se registra el cierre

#### Scenario: Wallet no confirmada
- **WHEN** la verificación está aprobada pero la consulta de la wallet falla o la wallet no está activa
- **THEN** la cuenta conserva el resultado aprobado, la interfaz informa que no se pudo confirmar la wallet sin declararla activa ni lista, y ofrece volver a consultar

#### Scenario: Solicitud incompleta
- **WHEN** falta el doble factor, la validación o la persistencia
- **THEN** la wallet no pasa a activa y no se registra el cierre como finalización

### Requirement: Salida con punto de entrada a pagos de bajo monto
El sistema SHALL mostrar, solo con la wallet activa confirmada, el punto de entrada a
pagos de bajo monto y SHALL exponer la finalización como señal una sola vez por
verificación mientras la pantalla siga abierta, y SHALL NOT iniciar ningún pago como
parte del onboarding. SHALL permitir terminar la sesión sin acceder a pagos.

#### Scenario: Onboarding completado
- **WHEN** se confirma una wallet activa
- **THEN** se muestra el punto de entrada a pagos de bajo monto y se dispara la señal de finalización sin iniciar un pago

#### Scenario: Consultas repetidas
- **WHEN** la persona vuelve a consultar una verificación cuya finalización ya se señaló
- **THEN** no se dispara la señal por segunda vez

#### Scenario: Sin entrada a pagos sin activación
- **WHEN** la verificación está pendiente, rechazada, aprobada sin wallet confirmada, con el doble factor incompleto o con error
- **THEN** no se muestra el punto de entrada a pagos ni se dispara la señal de finalización

#### Scenario: Terminar la sesión
- **WHEN** la persona elige terminar en lugar de continuar
- **THEN** se registra el cierre del flujo y no se inicia ningún pago

### Requirement: Verificación pendiente de revisión
El sistema SHALL mostrar una verificación pendiente como en revisión, SHALL permitir
consultar su estado actualizado desde la API y SHALL recordar solo su identificador
mientras la sesión del navegador continúe, sin ofrecer abandonar la revisión
mientras no se resuelva.

#### Scenario: Revisión pendiente
- **WHEN** el proveedor deja la verificación pendiente
- **THEN** se muestra que está en revisión, sin wallet activa, con una acción para actualizar el estado y sin una acción para empezar de nuevo

#### Scenario: Resolución posterior
- **WHEN** la persona actualiza el estado y la verificación ya fue aprobada
- **THEN** la cuenta pasa a activa, se muestra la wallet y se olvida el identificador pendiente

#### Scenario: Verificación desconocida
- **WHEN** se consulta un identificador que no pertenece a ninguna cuenta
- **THEN** la API responde `404` sin llamar al proveedor

### Requirement: Reanudación tras una interrupción
El sistema SHALL, al retomar un onboarding interrumpido, validar el estado persistido en
la API y continuar desde un paso seguro sin pedir de nuevo los datos ya validados, y
SHALL NOT marcar la wallet como activa ni registrar un cierre o una finalización de paso
que no ocurrió.

#### Scenario: Recarga con revisión pendiente
- **WHEN** la persona recarga la página mientras hay una verificación pendiente
- **THEN** el recorrido se retoma en el resultado con el estado consultado nuevamente

#### Scenario: Interrupción antes del doble factor
- **WHEN** la persona abandona el flujo antes de completar el segundo factor y vuelve
- **THEN** continúa desde el paso del doble factor sin cuenta activa ni eventos de finalización ficticios

#### Scenario: Reanudación fallida
- **WHEN** la persona recarga y no es posible consultar el estado pendiente
- **THEN** se informa del problema, se ofrece reintentar la consulta y no se permite iniciar otro registro hasta consultarla

### Requirement: Rechazo de la verificación
El sistema SHALL mostrar una verificación rechazada como rechazada, SHALL conservarla
en la cuenta y SHALL NOT mostrar una wallet activa.

#### Scenario: Verificación rechazada
- **WHEN** el proveedor rechaza la verificación
- **THEN** se informa del rechazo, no se muestra una wallet activa y el documento sigue contando como cuenta existente sin revelarlo a terceros

### Requirement: Errores recuperables del servicio
El sistema SHALL informar de los errores de validación, doble factor, límite, red,
servicio no disponible y fallas técnicas con un mensaje que permita actuar y ofrezca
reintentar o salir, y SHALL NOT presentar el onboarding como exitoso ni afirmar que se
creó una wallet si la persistencia o la activación fallaron o el proveedor no está
disponible.

#### Scenario: Proveedor no disponible
- **WHEN** el proveedor responde que no está disponible
- **THEN** la API responde `503`, la persona permanece en el paso actual, ve que no se creó ninguna wallet y puede reintentar

#### Scenario: Resultado incierto
- **WHEN** la llamada al proveedor falla o agota el tiempo y no se sabe si procesó la solicitud
- **THEN** la API responde `504`, libera el documento y la interfaz no afirma que no se creó ninguna wallet

#### Scenario: Límite del proveedor
- **WHEN** el proveedor responde que alcanzó su límite de uso
- **THEN** la API responde `429` y la interfaz muestra el mensaje de límite

#### Scenario: Falla de persistencia o activación
- **WHEN** no se pudo persistir la cuenta o activar la wallet
- **THEN** se informa que no se pudo completar el paso, se ofrece reintentar o salir y no se registra el cierre como éxito

#### Scenario: API inalcanzable
- **WHEN** no es posible conectar con la API
- **THEN** se informa del problema de conexión y se permite reintentar

### Requirement: Instrumentación del onboarding
El sistema SHALL registrar en el servidor el inicio del onboarding, la finalización de
cada paso y el cierre del flujo, cada evento con marca de tiempo suficiente para medir
duración, un identificador técnico del onboarding no sensible y el mínimo de datos. SHALL
NOT usar el número de documento como identificador ni incluirlo, junto con códigos de
verificación, secretos o credenciales, en un evento.

#### Scenario: Eventos de un flujo completo
- **WHEN** una persona completa el onboarding
- **THEN** existen eventos de inicio, de finalización de cada paso y de cierre, ordenados por marca de tiempo y vinculados por el mismo identificador técnico

#### Scenario: Flujo interrumpido
- **WHEN** el flujo se interrumpe antes de completarse
- **THEN** no existe un evento de cierre exitoso ni de finalización de pasos que no ocurrieron

#### Scenario: Eventos sin datos sensibles
- **WHEN** se inspeccionan los eventos, los logs y los mensajes de error
- **THEN** no contienen el número de documento, códigos de verificación, secretos ni credenciales

### Requirement: Salida analítica del onboarding
El sistema SHALL permitir revisar la mediana de duración, los nuevos usuarios activos por
mes y la atribución de gasto necesaria para CAC, usando la frontera analítica oficial de
inicio y fin una vez acordada, y SHALL mantener la finalización del onboarding separada del
evento de activación que emiten los pagos exitosos para MAU.

#### Scenario: Reporte sin frontera acordada
- **WHEN** la frontera analítica oficial de inicio y fin aún no está acordada
- **THEN** no se reporta la mediana frente al objetivo de 3 minutos

#### Scenario: Gasto de adquisición sin fuente
- **WHEN** no existe una fuente de gasto con reglas de atribución acordadas
- **THEN** la salida analítica no calcula CAC y declara que falta esa fuente

#### Scenario: Gasto de adquisición sin fuente
- **WHEN** no existe una fuente de gasto con reglas de atribución acordadas
- **THEN** la salida analítica no calcula CAC y declara que falta esa fuente

### Requirement: Seguridad y minimización de datos
El sistema SHALL transmitir los datos de documento y de autenticación por canales cifrados,
SHALL proteger los datos persistidos con controles de acceso y cifrado adecuados, SHALL
restringir su acceso a los componentes y personas autorizadas, SHALL recolectar solo el tipo
y el número de documento y SHALL NOT incluirlos, ni códigos de verificación, secretos o
credenciales, en logs, analítica ni mensajes de error.

#### Scenario: Datos persistidos
- **WHEN** se persiste una cuenta
- **THEN** el documento se guarda con protección y acceso restringido, y la unicidad se aplica sin exponer el valor

#### Scenario: Mensajes y logs
- **WHEN** ocurre un error de validación, de doble factor o técnico
- **THEN** el mensaje y el log no incluyen el documento, el código ni secretos

### Requirement: Alcance acotado y datos de prueba
El sistema SHALL usar únicamente documentos ficticios, SHALL NOT guardar el
documento en el navegador, SHALL NOT ejecutar pagos ni cobros QR como parte del onboarding
y SHALL NOT modificar el login heredado.

#### Scenario: Persistencia mínima en el navegador
- **WHEN** el recorrido guarda estado para retomarlo
- **THEN** solo guarda identificadores técnicos no sensibles en el almacenamiento de la sesión, nunca el documento ni códigos

#### Scenario: Sin pagos en el onboarding
- **WHEN** se completa el onboarding
- **THEN** no se crea ningún pago ni cobro y solo se ofrece el punto de entrada a pagos de bajo monto
