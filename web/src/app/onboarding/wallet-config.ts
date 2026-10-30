export const ONBOARDING_API_BASE_URL = 'http://localhost:8000';

export const ONBOARDING_REQUEST_TIMEOUT_MS = 15000;

// Es lo único que se guarda en el navegador: nunca el documento ni el código de verificación.
export const ONBOARDING_ID_STORAGE_KEY = 'wallet_onboarding_id';

export const TWO_FACTOR_CODE_LENGTH = 6;
export const TWO_FACTOR_CODE_PATTERN = new RegExp(`^\\d{${TWO_FACTOR_CODE_LENGTH}}$`);
