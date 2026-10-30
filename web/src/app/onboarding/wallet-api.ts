import { ONBOARDING_REQUEST_TIMEOUT_MS } from './wallet-config';

export type OnboardingScenario = 'APPROVED' | 'REJECTED' | 'MANUAL_REVIEW' | 'UNAVAILABLE';
export type ExitAction = 'CONTINUE' | 'END';
export type TwoFactorFailureReason = 'INCORRECT' | 'EXPIRED';

export type OnboardingApiStep = 'DOCUMENT' | 'TWO_FACTOR' | 'ACTIVATION' | 'EXIT';
export type RegistrationState = 'STARTED' | 'DOCUMENT_VALID' | 'PERSISTING' | 'PERSISTED';
export type VerificationState = 'PENDING' | 'CHALLENGED' | 'VERIFIED';
export type ActivationState = 'INACTIVE' | 'PENDING' | 'REJECTED' | 'ACTIVE';
export type ProviderState = 'ACTIVE' | 'PENDING' | 'REJECTED';

export interface OnboardingStates {
  registration: RegistrationState;
  verification: VerificationState;
  activation: ActivationState;
  provider: ProviderState | null;
}

export interface Wallet {
  id: string;
  status: string;
  balance: number;
  reserved: number;
  available: number;
  currency: string;
}

// `wallet` solo viene informada cuando la API pudo confirmarla con el proveedor.
export interface Onboarding {
  onboardingId: string;
  step: OnboardingApiStep;
  states: OnboardingStates;
  twoFactorAvailable: boolean;
  wallet: Wallet | null;
  paymentsEntryAvailable: boolean;
}

export type OnboardingApiErrorKind =
  | 'validation'
  | 'invalid-step'
  | 'registration-unavailable'
  | 'two-factor-failed'
  | 'two-factor-locked'
  | 'two-factor-limit'
  | 'two-factor-unavailable'
  | 'two-factor-required'
  | 'not-found'
  | 'limit'
  | 'unavailable'
  | 'unknown-result'
  | 'network'
  | 'unexpected';

export interface OnboardingApiErrorDetails {
  reason?: TwoFactorFailureReason;
  retryAfterSeconds?: number;
  // Solo la respuesta neutra de REGISTRATION_UNAVAILABLE trae un texto pensado para mostrarse.
  message?: string;
}

export class OnboardingApiError extends Error {
  readonly reason?: TwoFactorFailureReason;
  readonly retryAfterSeconds?: number;

  constructor(
    readonly kind: OnboardingApiErrorKind,
    details: OnboardingApiErrorDetails = {}
  ) {
    super(details.message ?? kind);
    this.name = 'OnboardingApiError';
    this.reason = details.reason;
    this.retryAfterSeconds = details.retryAfterSeconds;
  }
}

export interface OnboardingApi {
  start(): Promise<Onboarding>;
  get(onboardingId: string): Promise<Onboarding>;
  submitDocument(onboardingId: string, document: string, scenario: OnboardingScenario): Promise<Onboarding>;
  requestChallenge(onboardingId: string): Promise<Onboarding>;
  verifyTwoFactor(onboardingId: string, code: string): Promise<Onboarding>;
  activate(onboardingId: string): Promise<Onboarding>;
  exit(onboardingId: string, action: ExitAction): Promise<Onboarding>;
}

type FetchFn = (input: string, init?: RequestInit) => Promise<Response>;

const API_STEPS: readonly OnboardingApiStep[] = ['DOCUMENT', 'TWO_FACTOR', 'ACTIVATION', 'EXIT'];
const REGISTRATION_STATES: readonly RegistrationState[] = ['STARTED', 'DOCUMENT_VALID', 'PERSISTING', 'PERSISTED'];
const VERIFICATION_STATES: readonly VerificationState[] = ['PENDING', 'CHALLENGED', 'VERIFIED'];
const ACTIVATION_STATES: readonly ActivationState[] = ['INACTIVE', 'PENDING', 'REJECTED', 'ACTIVE'];
const PROVIDER_STATES: readonly ProviderState[] = ['ACTIVE', 'PENDING', 'REJECTED'];
const FAILURE_REASONS: readonly TwoFactorFailureReason[] = ['INCORRECT', 'EXPIRED'];

const ERROR_KIND_BY_STATUS = new Map<number, OnboardingApiErrorKind>([
  [400, 'validation'],
  [413, 'validation'],
  [422, 'validation'],
  [404, 'not-found'],
  [429, 'limit'],
  [502, 'unavailable'],
  [503, 'unavailable'],
  [504, 'unknown-result']
]);

// Algunos estados HTTP se reparten entre varios errores: los distingue `detail.error`.
const ERROR_KIND_BY_CODE = new Map<string, OnboardingApiErrorKind>([
  ['400:TWO_FACTOR_FAILED', 'two-factor-failed'],
  ['403:TWO_FACTOR_REQUIRED', 'two-factor-required'],
  ['409:INVALID_STEP', 'invalid-step'],
  ['409:REGISTRATION_UNAVAILABLE', 'registration-unavailable'],
  ['429:TWO_FACTOR_LOCKED', 'two-factor-locked'],
  ['429:TWO_FACTOR_LIMIT', 'two-factor-limit'],
  ['503:TWO_FACTOR_UNAVAILABLE', 'two-factor-unavailable']
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isAmount(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isOneOf<T extends string>(values: readonly T[], value: unknown): value is T {
  return typeof value === 'string' && (values as readonly string[]).includes(value);
}

function parseWallet(body: unknown): Wallet {
  if (
    isRecord(body) &&
    typeof body['id'] === 'string' &&
    typeof body['status'] === 'string' &&
    isAmount(body['balance']) &&
    isAmount(body['reserved']) &&
    isAmount(body['available']) &&
    typeof body['currency'] === 'string'
  ) {
    return {
      id: body['id'],
      status: body['status'],
      balance: body['balance'],
      reserved: body['reserved'],
      available: body['available'],
      currency: body['currency']
    };
  }
  throw new OnboardingApiError('unexpected');
}

function isProviderState(value: unknown): value is ProviderState | null {
  return value === null || isOneOf(PROVIDER_STATES, value);
}

function parseStates(body: unknown): OnboardingStates {
  if (!isRecord(body)) {
    throw new OnboardingApiError('unexpected');
  }
  const { registration, verification, activation, provider } = body;
  if (
    isOneOf(REGISTRATION_STATES, registration) &&
    isOneOf(VERIFICATION_STATES, verification) &&
    isOneOf(ACTIVATION_STATES, activation) &&
    isProviderState(provider)
  ) {
    return { registration, verification, activation, provider };
  }
  throw new OnboardingApiError('unexpected');
}

function parseOnboarding(body: unknown): Onboarding {
  if (
    isRecord(body) &&
    typeof body['onboardingId'] === 'string' &&
    isOneOf(API_STEPS, body['step']) &&
    typeof body['twoFactorAvailable'] === 'boolean' &&
    typeof body['paymentsEntryAvailable'] === 'boolean'
  ) {
    const wallet = body['wallet'];
    return {
      onboardingId: body['onboardingId'],
      step: body['step'],
      states: parseStates(body['states']),
      twoFactorAvailable: body['twoFactorAvailable'],
      wallet: wallet === null || wallet === undefined ? null : parseWallet(wallet),
      paymentsEntryAvailable: body['paymentsEntryAvailable']
    };
  }
  throw new OnboardingApiError('unexpected');
}

// FastAPI responde los errores de la API como {detail: {error, ...}} y los de validación como lista.
function errorDetail(body: unknown): Record<string, unknown> {
  return isRecord(body) && isRecord(body['detail']) && !Array.isArray(body['detail']) ? body['detail'] : {};
}

function errorDetails(kind: OnboardingApiErrorKind, detail: Record<string, unknown>): OnboardingApiErrorDetails {
  const { reason, retryAfterSeconds, message } = detail;
  if (kind === 'two-factor-failed') {
    return { reason: isOneOf(FAILURE_REASONS, reason) ? reason : undefined };
  }
  if (kind === 'two-factor-locked') {
    return { retryAfterSeconds: isAmount(retryAfterSeconds) && retryAfterSeconds > 0 ? retryAfterSeconds : undefined };
  }
  if (kind === 'registration-unavailable') {
    return { message: typeof message === 'string' && message.trim() !== '' ? message : undefined };
  }
  return {};
}

function toError(status: number, body: unknown): OnboardingApiError {
  const detail = errorDetail(body);
  const kind =
    ERROR_KIND_BY_CODE.get(`${status}:${String(detail['error'])}`) ?? ERROR_KIND_BY_STATUS.get(status) ?? 'unexpected';
  // Un 400 sin el código del segundo factor es un error de validación genérico.
  return new OnboardingApiError(kind, errorDetails(kind, detail));
}

export class HttpOnboardingApi implements OnboardingApi {
  constructor(
    private readonly baseUrl: string,
    private readonly fetchFn: FetchFn = (input, init) => fetch(input, init)
  ) {}

  start(): Promise<Onboarding> {
    return this.send('POST', '/api/onboarding');
  }

  get(onboardingId: string): Promise<Onboarding> {
    return this.send('GET', this.path(onboardingId));
  }

  submitDocument(onboardingId: string, document: string, scenario: OnboardingScenario): Promise<Onboarding> {
    return this.send('PUT', this.path(onboardingId, '/document'), { documentType: 'TEST', document, scenario });
  }

  requestChallenge(onboardingId: string): Promise<Onboarding> {
    return this.send('POST', this.path(onboardingId, '/challenge'));
  }

  verifyTwoFactor(onboardingId: string, code: string): Promise<Onboarding> {
    return this.send('POST', this.path(onboardingId, '/two-factor'), { code });
  }

  activate(onboardingId: string): Promise<Onboarding> {
    return this.send('POST', this.path(onboardingId, '/activate'));
  }

  exit(onboardingId: string, action: ExitAction): Promise<Onboarding> {
    return this.send('POST', this.path(onboardingId, '/exit'), { action });
  }

  private path(onboardingId: string, suffix = ''): string {
    return `/api/onboarding/${encodeURIComponent(onboardingId)}${suffix}`;
  }

  private async send(method: string, path: string, payload?: object): Promise<Onboarding> {
    const init: RequestInit =
      payload === undefined
        ? { method }
        : { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) };
    return parseOnboarding(await this.request(path, init));
  }

  private async request(path: string, init: RequestInit): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), ONBOARDING_REQUEST_TIMEOUT_MS);
    // El límite cubre también la lectura del cuerpo, no solo la llegada de las cabeceras.
    try {
      let response: Response;
      try {
        response = await this.fetchFn(`${this.baseUrl}${path}`, { ...init, signal: controller.signal });
      } catch {
        throw new OnboardingApiError('network');
      }

      let body: unknown = null;
      try {
        body = await response.json();
      } catch {
        if (controller.signal.aborted) {
          throw new OnboardingApiError('network');
        }
      }
      if (!response.ok) {
        throw toError(response.status, body);
      }
      return body;
    } finally {
      clearTimeout(timer);
    }
  }
}
