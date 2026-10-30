# Tasks

## 1. Recorrido de demostración

- [x] 1.1 Implementar transiciones y validación del nombre; verificar avance,
  bloqueo, retroceso, activación y reinicio con pruebas unitarias.
- [x] 1.2 Agregar ruta e interfaz adaptable con indicador de pasos y estado
  inequívocamente simulado; comprobar el recorrido en navegador y la compilación.
- [x] 1.3 Documentar cómo abrir la demostración y sus límites; verificar que no
  se prometen pagos, KYC, persistencia ni analítica.

## 2. Integración

- [x] 2.1 Ejecutar las pruebas web y la compilación; registrar los resultados
  reales sin marcar como cumplidos los criterios excluidos de la HU.
- [x] 2.2 Validar el cambio OpenSpec y conservar el borrador anterior intacto.

## Evidencia

- En `web/`, `npm test`: 10 pruebas aprobadas.
- En `web/`, `npm run test:coverage -- --coverage.include=src/app/onboarding/onboarding-flow.ts`:
  100% de líneas y ramas para el módulo de transiciones; no representa la
  cobertura de toda la aplicación.
- En `web/`, `npm run build`: aprobado; advertencias existentes por dependencias
  CommonJS de axios y lodash.
- Navegador: nombre inválido, revisión, activación y reinicio comprobados.
  En pantalla de 375 × 812 se comprobaron los indicadores y la pérdida de
  estado al recargar.
- En la raíz del producto, `openspec validate onboarding-wallet-demo --strict`:
  aprobado.

Los pagos reales y criterios 4, 5 y 6 de la HU no forman parte de esta
demostración y no se consideran cumplidos.
