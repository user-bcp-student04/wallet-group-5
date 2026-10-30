# Onboarding de la wallet (MVP Perú)

**Como usuario** de smartphone que realiza transferencias diarias de bajo monto,
**quiero** completar el onboarding de la wallet con un flujo guiado y señales claras de siguiente paso,
**para** poder empezar a pagar sin abandonar el proceso.

## Criterios de aceptación

1. El flujo de onboarding muestra la secuencia de pasos requeridos y el paso actual en todo momento.
2. Si falta información obligatoria o hay datos inválidos, el flujo bloquea el avance y muestra un mensaje accionable para corregir.
3. Cuando el onboarding finaliza correctamente, el estado de la wallet cambia a activo y el usuario puede acceder al punto de entrada de pagos de bajo monto.
4. El sistema registra eventos de inicio de onboarding, finalización de cada paso y cierre del flujo para analítica del MVP.
5. Para la cohorte MVP en Perú, el tiempo mediano de finalización de onboarding baja de 8 minutos a 3 minutos dentro del trimestre posterior al lanzamiento.
6. La salida analítica de onboarding incluye conteos mensuales de nuevos usuarios activos y la atribución de gasto de adquisición necesaria para verificar MAU entre 1,000 y 2,000 y CAC de PEN 10 por usuario nuevo en los primeros 3 meses.

## Contexto

- Épica: [MVP de wallet en Perú](https://github.com/users/user-bcp-student04/projects/6/epic/peru-wallet-mvp.sp.md).
- Esta historia contribuye directamente al objetivo de la épica: reducir el tiempo de finalización de onboarding de 8 minutos a 3 minutos.
- Esta historia captura la instrumentación de adquisición/activación necesaria para seguir MAU (1,000-2,000) y CAC (PEN 10) en meses 1-3.
- La historia se apoya en el tamaño de oportunidad documentado para comportamiento wallet interoperable en Perú.
- El MVP debe alinearse con expectativas de usabilidad y continuidad en pagos inmediatos.

## Supuestos

- Para la verificación de identidad y documentos solo considerar Tipo y número de documento de la persona como requisitos.
- Como consideración técnica, la frontera de duración no debe ser mas de 3 minutos.
- Como consideración técnica, el completar el onboarding debe ser desencadenador para seguir con los demás pasos como los pago de bajo monto.
- La autenticación deberá ser por doble factor.
- Debe evitar usuarios/cuentas duplicadas, es decir, debe implementar la persistencia de cuentas.
- El rango objetivo de MAU (1,000-2,000) y el objetivo de CAC (PEN 10) fueron definidos por el Product Owner.

## Decisiones de alcance de esta entrega

La entrega es una simulación sobre el simulador de wallet
(`docs/contracts/bcp-wallet-mock-openapi.yaml`) y está especificada en
`openspec/changes/onboarding-wallet-demo`. El procedimiento
[onboarding-wallet-procedimiento.md](onboarding-wallet-procedimiento.md) amplía el alcance
anterior: el doble factor, el punto de entrada a pagos de bajo monto y la instrumentación
del onboarding (criterios 3 y 4) pasan a estar **en alcance**.

- **Decisiones tomadas solo para la simulación, por aprobar** (ver `design.md`): doble
  factor con un código de prueba por entorno, frontera analítica `onboarding.started` →
  `onboarding.closed` con la wallet activa y un texto configurable para el canal de asistencia.
  Siguen abiertos el origen y las reglas de atribución del gasto de adquisición (CAC) y, para un
  lanzamiento real, el mecanismo de doble factor aprobado.
- **Fuera de alcance:** ejecución de pagos, cobros QR y el evento de activación para MAU, que
  emiten los pagos exitosos (historia de confirmación de pagos).
- **Interpretación a confirmar:** la «frontera de duración» de 3 minutos es un objetivo de
  diseño; solo se reporta la mediana cuando la frontera analítica esté acordada.
- El resultado de la verificación se elige con un selector de pruebas; solo se admiten documentos
  ficticios (`TEST-…`).
