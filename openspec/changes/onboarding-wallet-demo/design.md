# Design

## Context

La HU solicita un onboarding de wallet con activación, entrada a pagos y
medición de resultados. El solicitante acotó esta entrega a una demostración:
nombre visible, revisión y activación simulada; el home y toda la analítica
quedan fuera. KYC y requisitos para operaciones reales siguen sin definir.

## Goals / Non-Goals

**Goals:** un recorrido móvil y accesible, validación verificable, indicador
persistente del paso y estado de demostración inequívoco.

**Non-Goals:** cuenta o wallet real, KYC, pagos, home, persistencia, correo,
instrumentación, métricas de producto o modificación del sistema heredado.

## Decisions

- Agregar una ruta Angular independiente y un enlace desde el login heredado.
  No se altera el comportamiento de login ni se reutiliza el dashboard como
  home de pagos.
- Modelar la secuencia en memoria, con validación en la transición y una pantalla
  final de activación simulada. Recargar o reiniciar borra el estado; no se
  escriben datos en localStorage ni se invocan servicios externos.
- Mantener las reglas de transición en una clase TypeScript independiente para
  probar validaciones, avance, retroceso y reinicio sin un backend.
- Mostrar la naturaleza simulada y la ausencia de pagos en la interfaz. Nunca
  presentar la activación como una verificación de identidad real.

## Risks / Trade-offs

- El estado no sobrevive a una recarga. Esto es intencional en la demostración,
  no una implementación de continuidad de producción.
- Los criterios 4, 5 y 6 y el acceso real a pagos siguen sin implementar. Los
  objetivos de métricas solo pueden evaluarse con datos posteriores al lanzamiento.
- El borrador `onboarding-wallet` tiene un alcance distinto y se conserva sin
  alterarlo; antes de una versión real habrá que reconciliar ambos cambios.

## Migration Plan

La ruta nueva no requiere migraciones ni afecta datos existentes. Se puede
retirar el enlace y la ruta para deshabilitar la demostración.
