import { OnboardingApiError } from './wallet-api';
import { TWO_FACTOR_CODE_LENGTH } from './wallet-config';

export type FlowAction = 'start' | 'load' | 'document' | 'challenge' | 'verify' | 'activate' | 'exit';

export const INVALID_DOCUMENT_MESSAGE =
  'Ingresa un documento ficticio que empiece con TEST- seguido de un código, por ejemplo TEST-001 (máximo 200 caracteres).';
export const INVALID_CODE_MESSAGE = `Ingresa el código de verificación de ${TWO_FACTOR_CODE_LENGTH} dígitos, solo con números.`;
export const NEW_CODE_SENT_MESSAGE = 'Enviamos un nuevo código de verificación.';
export const SESSION_FINISHED_MESSAGE = 'Terminaste tu sesión de onboarding. Puedes iniciar otro registro cuando quieras.';
export const PENDING_BLOCKS_NEW_REGISTRATION_MESSAGE =
  'Tienes un registro en curso que no pudimos consultar. Consulta su estado antes de iniciar otro.';
export const TWO_FACTOR_NOT_CONFIGURED_MESSAGE =
  'El doble factor no está configurado en este entorno, por lo que no podemos verificar tu identidad ni continuar con el registro.';

const REGISTRATION_ORIENTATION_MESSAGE =
  'Usa el canal de acceso habitual o contacta con asistencia para continuar.';
const TWO_FACTOR_UNAVAILABLE_MESSAGE =
  'El mecanismo de doble factor no está disponible en este momento. No puedes continuar hasta que se restablezca; inténtalo más tarde.';

function lockedMessage(retryAfterSeconds?: number): string {
  if (retryAfterSeconds === undefined) {
    return 'El doble factor está bloqueado temporalmente. Espera unos minutos antes de intentarlo de nuevo.';
  }
  const unit = retryAfterSeconds === 1 ? 'segundo' : 'segundos';
  return `El doble factor está bloqueado temporalmente. Espera ${retryAfterSeconds} ${unit} antes de intentarlo de nuevo.`;
}

function failedCodeMessage(error: OnboardingApiError): string {
  if (error.reason === 'INCORRECT') {
    return `El código no es correcto. Revisa los ${TWO_FACTOR_CODE_LENGTH} dígitos e inténtalo de nuevo.`;
  }
  if (error.reason === 'EXPIRED') {
    return 'El código expiró. Solicita un nuevo código para continuar.';
  }
  return 'No se pudo verificar el código. Inténtalo de nuevo.';
}

function validationMessage(action: FlowAction): string {
  if (action === 'document') {
    return 'El servicio no aceptó el documento. Revisa que empiece con TEST- y vuelve a intentarlo.';
  }
  if (action === 'verify') {
    return `El servicio no aceptó el código. Debe tener exactamente ${TWO_FACTOR_CODE_LENGTH} dígitos.`;
  }
  return 'El servicio no aceptó la solicitud. Inténtalo de nuevo.';
}

function unavailableMessage(action: FlowAction): string {
  return action === 'activate'
    ? 'El servicio de verificación no está disponible. No se activó ninguna wallet; inténtalo nuevamente.'
    : 'El servicio no está disponible. Inténtalo nuevamente en unos momentos.';
}

function unknownResultMessage(action: FlowAction): string {
  return action === 'activate'
    ? 'No pudimos confirmar el resultado de la activación. Inténtalo de nuevo; no mostraremos tu wallet hasta que esté confirmada.'
    : 'No se pudo completar la operación a tiempo. Inténtalo de nuevo.';
}

function registrationUnavailableMessage(error: OnboardingApiError): string {
  // La API no confirma si existe una cuenta: se muestra su texto neutral, sin interpretarlo.
  return error.message === error.kind ? REGISTRATION_ORIENTATION_MESSAGE : error.message;
}

export function describeError(error: unknown, action: FlowAction): string {
  if (!(error instanceof OnboardingApiError)) {
    return 'El servicio respondió de forma inesperada. Inténtalo de nuevo.';
  }
  switch (error.kind) {
    case 'validation':
      return validationMessage(action);
    case 'invalid-step':
      return 'Ese paso ya no corresponde a tu registro. Actualizamos tu estado para que continúes desde donde corresponde.';
    case 'registration-unavailable':
      return registrationUnavailableMessage(error);
    case 'two-factor-failed':
      return failedCodeMessage(error);
    case 'two-factor-locked':
      return lockedMessage(error.retryAfterSeconds);
    case 'two-factor-limit':
      return 'Alcanzaste el límite de envíos de códigos. Inténtalo más tarde o contacta con asistencia.';
    case 'two-factor-unavailable':
      return TWO_FACTOR_UNAVAILABLE_MESSAGE;
    case 'two-factor-required':
      return 'Debes verificar el doble factor antes de activar tu wallet.';
    case 'not-found':
      return 'No se encontró el registro. Inicia el proceso nuevamente.';
    case 'limit':
      return 'Se alcanzó el límite del servicio de verificación. Inténtalo más tarde.';
    case 'unavailable':
      return unavailableMessage(action);
    case 'unknown-result':
      return unknownResultMessage(action);
    case 'network':
      return 'No se pudo conectar con el servicio de onboarding. Verifica que esté iniciado e inténtalo de nuevo.';
    default:
      return 'El servicio respondió de forma inesperada. Inténtalo de nuevo.';
  }
}
