import { describe, expect, it, vi } from 'vitest';
import { DOCUMENT_NOT_REMEMBERED_LABEL, OnboardingFlow, ONBOARDING_STEPS } from './onboarding-flow';
import { PendingStore } from './pending-store';
import {
  ActivationState,
  Onboarding,
  OnboardingApi,
  OnboardingApiError,
  OnboardingApiErrorDetails,
  OnboardingApiErrorKind,
  OnboardingApiStep,
  ProviderState,
  VerificationState,
  Wallet
} from './wallet-api';

const ONBOARDING_ID = 'onb-1';
const SECRET_DOCUMENT = 'TEST-SECRET-001';
const SECRET_CODE = '654321';

const wallet: Wallet = { id: 'wal-1', status: 'ACTIVE', balance: 100, reserved: 0, available: 100, currency: 'PEN' };

interface StateOptions {
  verification?: VerificationState;
  activation?: ActivationState;
  provider?: ProviderState | null;
  wallet?: Wallet | null;
  twoFactorAvailable?: boolean;
  paymentsEntryAvailable?: boolean;
}

function state(step: OnboardingApiStep, options: StateOptions = {}): Onboarding {
  return {
    onboardingId: ONBOARDING_ID,
    step,
    states: {
      registration: step === 'DOCUMENT' ? 'STARTED' : 'DOCUMENT_VALID',
      verification: options.verification ?? 'PENDING',
      activation: options.activation ?? 'INACTIVE',
      provider: options.provider ?? null
    },
    twoFactorAvailable: options.twoFactorAvailable ?? true,
    wallet: options.wallet ?? null,
    paymentsEntryAvailable: options.paymentsEntryAvailable ?? false
  };
}

const documentState = state('DOCUMENT');
const twoFactorState = state('TWO_FACTOR', { verification: 'CHALLENGED' });
const activationState = state('ACTIVATION', { verification: 'VERIFIED' });
const exitState = state('EXIT', {
  verification: 'VERIFIED',
  activation: 'ACTIVE',
  provider: 'ACTIVE',
  wallet,
  paymentsEntryAvailable: true
});
const unconfirmedState = state('ACTIVATION', { verification: 'VERIFIED', provider: 'ACTIVE' });
const reviewState = state('ACTIVATION', { verification: 'VERIFIED', activation: 'PENDING', provider: 'PENDING' });
const rejectedState = state('ACTIVATION', { verification: 'VERIFIED', activation: 'REJECTED', provider: 'REJECTED' });

interface MemoryStore extends PendingStore {
  value: string | null;
  writes: string[];
}

function memoryStore(initial: string | null = null): MemoryStore {
  const store: MemoryStore = {
    value: initial,
    writes: [],
    read: () => store.value,
    write: (id: string) => {
      store.writes.push(id);
      store.value = id;
    },
    clear: () => {
      store.value = null;
    }
  };
  return store;
}

function fakeApi(overrides: Partial<OnboardingApi> = {}): OnboardingApi {
  return {
    start: vi.fn(async () => documentState),
    get: vi.fn(async () => exitState),
    submitDocument: vi.fn(async () => twoFactorState),
    requestChallenge: vi.fn(async () => twoFactorState),
    verifyTwoFactor: vi.fn(async () => activationState),
    activate: vi.fn(async () => exitState),
    exit: vi.fn(async () => exitState),
    ...overrides
  };
}

const failing = (kind: OnboardingApiErrorKind, details?: OnboardingApiErrorDetails) => async (): Promise<Onboarding> => {
  throw new OnboardingApiError(kind, details);
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

async function atDocument(api = fakeApi(), store = memoryStore(), onCompleted?: (state: Onboarding) => void) {
  const flow = new OnboardingFlow(api, store, onCompleted);
  await flow.start();
  return { flow, store, api };
}

async function atTwoFactor(api = fakeApi(), store = memoryStore(), onCompleted?: (state: Onboarding) => void) {
  const context = await atDocument(api, store, onCompleted);
  context.flow.document = SECRET_DOCUMENT;
  await context.flow.submitDocument();
  return context;
}

async function atActivation(api = fakeApi(), store = memoryStore(), onCompleted?: (state: Onboarding) => void) {
  const context = await atTwoFactor(api, store, onCompleted);
  context.flow.code = SECRET_CODE;
  await context.flow.verifyTwoFactor();
  return context;
}

describe('OnboardingFlow start', () => {
  it('shows the five steps and begins at the start step', () => {
    const flow = new OnboardingFlow(fakeApi(), memoryStore());
    expect(ONBOARDING_STEPS.map((item) => item.label)).toEqual(['Inicio', 'Documento', 'Doble factor', 'Activación', 'Salida']);
    expect(flow.step).toBe('start');
    expect(flow.documentType).toBe('TEST');
    expect(flow.scenario).toBe('APPROVED');
  });

  it('starts the onboarding and keeps only its id in the store', async () => {
    const { flow, store } = await atDocument();
    expect(flow.step).toBe('document');
    expect(store.writes).toEqual([ONBOARDING_ID]);
  });

  it('sends a single request when start is pressed twice', async () => {
    const gate = deferred<Onboarding>();
    const api = fakeApi({ start: vi.fn(() => gate.promise) });
    const flow = new OnboardingFlow(api, memoryStore());
    const first = flow.start();
    await flow.start();
    expect(flow.busy).toBe(true);
    gate.resolve(documentState);
    await first;
    expect(api.start).toHaveBeenCalledTimes(1);
    expect(flow.busy).toBe(false);
  });

  it('does not start again once the onboarding is in progress', async () => {
    const { flow, api } = await atDocument();
    await flow.start();
    expect(api.start).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['network', 'conectar'],
    ['unavailable', 'no está disponible'],
    ['limit', 'límite']
  ] as const)('stays at the start with a retry message when start fails with %s', async (kind, text) => {
    const store = memoryStore();
    const flow = new OnboardingFlow(fakeApi({ start: failing(kind) }), store);
    await flow.start();
    expect(flow.step).toBe('start');
    expect(flow.error).toContain(text);
    expect(store.writes).toEqual([]);
  });
});

describe('OnboardingFlow document step', () => {
  it.each(['', '   ', 'test-001', 'DOC-001', 'TEST-', ' TEST- ', 'TEST-' + 'x'.repeat(196)])(
    'blocks invalid document %j next to the field and keeps the value',
    async (document) => {
      const { flow, api } = await atDocument();
      flow.document = document;
      await flow.submitDocument();
      expect(flow.step).toBe('document');
      expect(flow.error).toContain('TEST-');
      expect(flow.document).toBe(document);
      expect(api.submitDocument).not.toHaveBeenCalled();
    }
  );

  it.each(['TEST-1', 'TEST-' + 'x'.repeat(195)])('trims and submits a valid document', async (document) => {
    const { flow, api } = await atDocument();
    flow.document = `  ${document}  `;
    flow.scenario = 'MANUAL_REVIEW';
    await flow.submitDocument();
    expect(api.submitDocument).toHaveBeenCalledWith(ONBOARDING_ID, document, 'MANUAL_REVIEW');
    expect(flow.document).toBe(document);
    expect(flow.step).toBe('two-factor');
    expect(flow.error).toBe('');
  });

  it('ignores the submit outside the document step', async () => {
    const flow = new OnboardingFlow(fakeApi(), memoryStore());
    flow.document = 'TEST-001';
    await flow.submitDocument();
    const { flow: inTwoFactor, api } = await atTwoFactor();
    await inTwoFactor.submitDocument();
    expect(api.submitDocument).toHaveBeenCalledTimes(1);
  });

  it('sends a single request on a double submit', async () => {
    const gate = deferred<Onboarding>();
    const api = fakeApi({ submitDocument: vi.fn(() => gate.promise) });
    const { flow } = await atDocument(api);
    flow.document = 'TEST-001';
    const first = flow.submitDocument();
    await flow.submitDocument();
    gate.resolve(twoFactorState);
    await first;
    expect(api.submitDocument).toHaveBeenCalledTimes(1);
  });

  it('keeps the typed value and explains an API validation failure', async () => {
    const api = fakeApi({ submitDocument: failing('validation') });
    const { flow } = await atDocument(api);
    flow.document = 'TEST-001';
    await flow.submitDocument();
    expect(flow.step).toBe('document');
    expect(flow.document).toBe('TEST-001');
    expect(flow.error).toContain('TEST-');
  });

  it.each([
    ['two-factor-locked', { retryAfterSeconds: 45 }, '45 segundos'],
    ['two-factor-locked', { retryAfterSeconds: 1 }, '1 segundo '],
    ['two-factor-locked', undefined, 'unos minutos'],
    ['two-factor-limit', undefined, 'límite de envíos']
  ] as const)('moves on to the second factor when the saved document hits %s', async (kind, details, text) => {
    const api = fakeApi({ submitDocument: failing(kind, details), get: vi.fn(async () => twoFactorState) });
    const { flow } = await atDocument(api);
    flow.document = 'TEST-001';
    await flow.submitDocument();
    expect(api.get).toHaveBeenCalledWith(ONBOARDING_ID);
    expect(flow.step).toBe('two-factor');
    expect(flow.error).toContain(text);
  });

  it('keeps the message when the state cannot be refreshed after a lock', async () => {
    const api = fakeApi({
      submitDocument: failing('two-factor-locked', { retryAfterSeconds: 5 }),
      get: failing('network')
    });
    const { flow } = await atDocument(api);
    flow.document = 'TEST-001';
    await flow.submitDocument();
    expect(flow.step).toBe('document');
    expect(flow.error).toContain('5 segundos');
  });

  it('warns when the second factor is not configured', async () => {
    const api = fakeApi({ start: vi.fn(async () => state('DOCUMENT', { twoFactorAvailable: false })) });
    const { flow } = await atDocument(api);
    expect(flow.twoFactorBlocked).toBe(true);
  });
});

describe('OnboardingFlow second factor', () => {
  it.each(['', '12345', '1234567', 'abcdef', '12 456', '１２３４５６'])('blocks invalid code %j without calling the API', async (code) => {
    const { flow, api } = await atTwoFactor();
    flow.code = code;
    await flow.verifyTwoFactor();
    expect(flow.step).toBe('two-factor');
    expect(flow.error).toContain('6 dígitos');
    expect(flow.code).toBe(code);
    expect(api.verifyTwoFactor).not.toHaveBeenCalled();
  });

  it('verifies the code, moves to activation and forgets the code', async () => {
    const { flow, api } = await atTwoFactor();
    flow.code = ` ${SECRET_CODE} `;
    await flow.verifyTwoFactor();
    expect(api.verifyTwoFactor).toHaveBeenCalledWith(ONBOARDING_ID, SECRET_CODE);
    expect(flow.step).toBe('activation');
    expect(flow.code).toBe('');
  });

  it('sends a single verification on a double click', async () => {
    const gate = deferred<Onboarding>();
    const api = fakeApi({ verifyTwoFactor: vi.fn(() => gate.promise) });
    const { flow } = await atTwoFactor(api);
    flow.code = SECRET_CODE;
    const first = flow.verifyTwoFactor();
    await flow.verifyTwoFactor();
    gate.resolve(activationState);
    await first;
    expect(api.verifyTwoFactor).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['INCORRECT', 'no es correcto'],
    ['EXPIRED', 'expiró'],
    [undefined, 'No se pudo verificar']
  ] as const)('explains a rejected code with reason %s and stays in place', async (reason, text) => {
    const api = fakeApi({ verifyTwoFactor: failing('two-factor-failed', { reason }) });
    const { flow } = await atTwoFactor(api);
    flow.code = SECRET_CODE;
    await flow.verifyTwoFactor();
    expect(flow.step).toBe('two-factor');
    expect(flow.error).toContain(text);
    expect(flow.code).toBe('');
  });

  it('tells how long to wait when the second factor is locked', async () => {
    const api = fakeApi({ verifyTwoFactor: failing('two-factor-locked', { retryAfterSeconds: 120 }) });
    const { flow } = await atTwoFactor(api);
    flow.code = SECRET_CODE;
    await flow.verifyTwoFactor();
    expect(flow.error).toContain('120 segundos');
    expect(flow.step).toBe('two-factor');
  });

  it.each([
    ['two-factor-unavailable', 'no está disponible'],
    ['validation', 'exactamente 6 dígitos'],
    ['network', 'conectar'],
    ['unexpected', 'inesperada']
  ] as const)('reports %s without advancing', async (kind, text) => {
    const api = fakeApi({ verifyTwoFactor: failing(kind) });
    const { flow } = await atTwoFactor(api);
    flow.code = SECRET_CODE;
    await flow.verifyTwoFactor();
    expect(flow.step).toBe('two-factor');
    expect(flow.error).toContain(text);
  });

  it('refreshes the step from the API when the verification is out of order', async () => {
    const api = fakeApi({ verifyTwoFactor: failing('invalid-step'), get: vi.fn(async () => activationState) });
    const { flow } = await atTwoFactor(api);
    flow.code = SECRET_CODE;
    await flow.verifyTwoFactor();
    expect(flow.step).toBe('activation');
    expect(flow.error).toContain('ya no corresponde');
  });

  it('does not declare or allow the second factor when it is not configured', async () => {
    const api = fakeApi({ submitDocument: vi.fn(async () => state('TWO_FACTOR', { twoFactorAvailable: false })) });
    const { flow } = await atTwoFactor(api);
    expect(flow.twoFactorBlocked).toBe(true);
    flow.code = SECRET_CODE;
    await flow.verifyTwoFactor();
    expect(flow.error).toContain('no está configurado');
    await flow.resendCode();
    expect(flow.error).toContain('no está configurado');
    expect(api.verifyTwoFactor).not.toHaveBeenCalled();
    expect(api.requestChallenge).not.toHaveBeenCalled();
    expect(flow.step).toBe('two-factor');
  });

  it('sends a new code and confirms it without keeping the old one', async () => {
    const { flow, api } = await atTwoFactor();
    flow.code = '111111';
    await flow.resendCode();
    expect(api.requestChallenge).toHaveBeenCalledWith(ONBOARDING_ID);
    expect(flow.notice).toContain('nuevo código');
    expect(flow.code).toBe('');
  });

  it.each([
    ['two-factor-limit', 'límite de envíos'],
    ['two-factor-locked', 'bloqueado'],
    ['two-factor-unavailable', 'no está disponible']
  ] as const)('explains a failed resend (%s)', async (kind, text) => {
    const api = fakeApi({ requestChallenge: failing(kind) });
    const { flow } = await atTwoFactor(api);
    await flow.resendCode();
    expect(flow.error).toContain(text);
    expect(flow.notice).toBe('');
    expect(flow.step).toBe('two-factor');
  });

  it('ignores resend outside the second factor step and while busy', async () => {
    const gate = deferred<Onboarding>();
    const api = fakeApi({ requestChallenge: vi.fn(() => gate.promise) });
    const { flow } = await atDocument(api);
    await flow.resendCode();
    expect(api.requestChallenge).not.toHaveBeenCalled();
    flow.document = 'TEST-001';
    await flow.submitDocument();
    const first = flow.resendCode();
    await flow.resendCode();
    gate.resolve(twoFactorState);
    await first;
    expect(api.requestChallenge).toHaveBeenCalledTimes(1);
  });
});

describe('OnboardingFlow going back to the document', () => {
  it('lets the person edit without typing the document again', async () => {
    const { flow, api } = await atTwoFactor();
    flow.editDocument();
    expect(flow.step).toBe('document');
    expect(flow.isEditingDocument).toBe(true);
    expect(flow.document).toBe(SECRET_DOCUMENT);
    await flow.submitDocument();
    expect(api.submitDocument).toHaveBeenLastCalledWith(ONBOARDING_ID, SECRET_DOCUMENT, 'APPROVED');
    expect(flow.step).toBe('two-factor');
    expect(flow.isEditingDocument).toBe(false);
  });

  it('can cancel the edit and return to the second factor', async () => {
    const { flow, api } = await atTwoFactor();
    flow.editDocument();
    flow.cancelEditDocument();
    expect(flow.step).toBe('two-factor');
    expect(flow.document).toBe(SECRET_DOCUMENT);
    expect(api.submitDocument).toHaveBeenCalledTimes(1);
  });

  it('keeps the edit open and the value when the new document is invalid', async () => {
    const { flow } = await atTwoFactor();
    flow.editDocument();
    flow.document = 'bad';
    await flow.submitDocument();
    expect(flow.step).toBe('document');
    expect(flow.document).toBe('bad');
    expect(flow.error).toContain('TEST-');
  });

  it('cannot go back from other steps nor cancel when not editing', async () => {
    const { flow } = await atActivation();
    flow.editDocument();
    flow.cancelEditDocument();
    expect(flow.step).toBe('activation');
    expect(flow.canEditDocument).toBe(false);
  });
});

describe('OnboardingFlow activation', () => {
  it('summarises the captured data before confirming', async () => {
    const { flow } = await atActivation();
    expect(flow.step).toBe('activation');
    expect(flow.activationOutcome).toBe('ready');
    expect(flow.documentSummary).toBe(SECRET_DOCUMENT);
    expect(flow.needsFollowUp).toBe(false);
  });

  it('does not show a number that was never captured in this page', async () => {
    const store = memoryStore(ONBOARDING_ID);
    const flow = new OnboardingFlow(fakeApi({ get: vi.fn(async () => activationState) }), store);
    await flow.resume();
    expect(flow.documentSummary).toBe(DOCUMENT_NOT_REMEMBERED_LABEL);
  });

  it('activates with a single request on a double click and finishes at the exit', async () => {
    const gate = deferred<Onboarding>();
    const api = fakeApi({ activate: vi.fn(() => gate.promise) });
    const { flow } = await atActivation(api);
    const first = flow.activate();
    await flow.activate();
    gate.resolve(exitState);
    await first;
    expect(api.activate).toHaveBeenCalledTimes(1);
    expect(flow.step).toBe('exit');
    expect(flow.wallet).toEqual(wallet);
  });

  it('ignores activation outside its step', async () => {
    const { flow, api } = await atTwoFactor();
    await flow.activate();
    expect(api.activate).not.toHaveBeenCalled();
  });

  it('shows an approved result without a confirmed wallet and offers a refresh', async () => {
    const api = fakeApi({ activate: vi.fn(async () => unconfirmedState) });
    const { flow, store } = await atActivation(api);
    await flow.activate();
    expect(flow.step).toBe('activation');
    expect(flow.activationOutcome).toBe('unconfirmed');
    expect(flow.wallet).toBeNull();
    expect(flow.needsFollowUp).toBe(true);
    expect(flow.paymentsEntryAvailable).toBe(false);
    expect(store.value).toBe(ONBOARDING_ID);
  });

  it('keeps a review pending, refuses to start over and follows it up', async () => {
    const api = fakeApi({ activate: vi.fn(async () => reviewState), get: vi.fn(async () => exitState) });
    const { flow, store } = await atActivation(api);
    await flow.activate();
    expect(flow.activationOutcome).toBe('in-review');
    expect(flow.needsFollowUp).toBe(true);
    flow.reset();
    expect(flow.step).toBe('activation');
    expect(store.value).toBe(ONBOARDING_ID);
    await flow.activate();
    expect(api.activate).toHaveBeenCalledTimes(1);
    await flow.refresh();
    expect(flow.step).toBe('exit');
  });

  it('keeps waiting when a refresh still finds the review pending', async () => {
    const api = fakeApi({ activate: vi.fn(async () => reviewState), get: vi.fn(async () => reviewState) });
    const { flow } = await atActivation(api);
    await flow.activate();
    await flow.refresh();
    expect(flow.activationOutcome).toBe('in-review');
    expect(flow.error).toBe('');
  });

  it('reports a failed refresh and keeps what was already shown', async () => {
    const api = fakeApi({ activate: vi.fn(async () => unconfirmedState), get: failing('unavailable') });
    const { flow } = await atActivation(api);
    await flow.activate();
    await flow.refresh();
    expect(flow.activationOutcome).toBe('unconfirmed');
    expect(flow.error).toContain('no está disponible');
    expect(flow.recoverableId).toBeNull();
  });

  it('ignores a refresh when there is nothing to follow up', async () => {
    const { flow, api } = await atActivation();
    await flow.refresh();
    expect(api.get).not.toHaveBeenCalled();
  });

  it('shows a rejection without wallet or payments entry and allows a fresh start', async () => {
    const api = fakeApi({ activate: vi.fn(async () => rejectedState) });
    const { flow, store } = await atActivation(api);
    await flow.activate();
    expect(flow.activationOutcome).toBe('rejected');
    expect(flow.wallet).toBeNull();
    expect(flow.paymentsEntryAvailable).toBe(false);
    flow.reset();
    expect(flow.step).toBe('start');
    expect(flow.document).toBe('');
    expect(store.value).toBeNull();
  });

  it('shows the neutral message and never reveals an existing account', async () => {
    const neutral = 'No fue posible completar el registro con los datos enviados.';
    const api = fakeApi({ activate: failing('registration-unavailable', { message: neutral }) });
    const { flow } = await atActivation(api);
    await flow.activate();
    expect(flow.step).toBe('activation');
    expect(flow.error).toBe(neutral);
    expect(flow.error.toLowerCase()).not.toMatch(/ya existe|existente|activa|pendiente|rechazad/);
    expect(flow.wallet).toBeNull();
  });

  it('falls back to a neutral text when the API gives no message', async () => {
    const api = fakeApi({ activate: failing('registration-unavailable') });
    const { flow } = await atActivation(api);
    await flow.activate();
    expect(flow.error).toContain('asistencia');
    expect(flow.error).not.toContain('registration-unavailable');
    expect(flow.error.toLowerCase()).not.toContain('ya existe');
  });

  it.each([
    ['unavailable', 'No se activó ninguna wallet'],
    ['unknown-result', 'no mostraremos tu wallet'],
    ['limit', 'límite'],
    ['unexpected', 'inesperada']
  ] as const)('never presents success when activation fails with %s', async (kind, text) => {
    const api = fakeApi({ activate: failing(kind) });
    const { flow } = await atActivation(api);
    await flow.activate();
    expect(flow.step).toBe('activation');
    expect(flow.activationOutcome).toBe('ready');
    expect(flow.wallet).toBeNull();
    expect(flow.error).toContain(text);
  });

  it('goes back to the second factor when the API says it is still required', async () => {
    const api = fakeApi({ activate: failing('two-factor-required'), get: vi.fn(async () => twoFactorState) });
    const { flow } = await atActivation(api);
    await flow.activate();
    expect(flow.step).toBe('two-factor');
    expect(flow.error).toContain('doble factor');
  });
});

describe('OnboardingFlow exit', () => {
  it('shows the confirmed wallet and the payments entry only when the API allows it', async () => {
    const { flow } = await atActivation();
    await flow.activate();
    expect(flow.wallet).toEqual(wallet);
    expect(flow.paymentsEntryAvailable).toBe(true);

    const closed = fakeApi({ activate: vi.fn(async () => ({ ...exitState, paymentsEntryAvailable: false })) });
    const { flow: withoutEntry } = await atActivation(closed);
    await withoutEntry.activate();
    expect(withoutEntry.wallet).toEqual(wallet);
    expect(withoutEntry.paymentsEntryAvailable).toBe(false);
  });

  it('hides the entry and the wallet when the wallet is not confirmed', async () => {
    const unconfirmedExit = { ...exitState, wallet: null };
    const api = fakeApi({ activate: vi.fn(async () => unconfirmedExit) });
    const onCompleted = vi.fn();
    const { flow } = await atActivation(api, memoryStore(), onCompleted);
    await flow.activate();
    expect(flow.wallet).toBeNull();
    expect(flow.paymentsEntryAvailable).toBe(false);
    expect(onCompleted).not.toHaveBeenCalled();
  });

  it('does not accept a wallet that is not active', async () => {
    const frozen = { ...exitState, wallet: { ...wallet, status: 'FROZEN' } };
    const { flow } = await atActivation(fakeApi({ activate: vi.fn(async () => frozen) }));
    await flow.activate();
    expect(flow.wallet).toBeNull();
  });

  it('opens the payments entry without starting any payment', async () => {
    const onCompleted = vi.fn();
    const { flow, api, store } = await atActivation(fakeApi(), memoryStore(), onCompleted);
    await flow.activate();
    await flow.openPayments();
    expect(api.exit).toHaveBeenCalledWith(ONBOARDING_ID, 'CONTINUE');
    expect(flow.paymentsEntryOpened).toBe(true);
    expect(flow.step).toBe('exit');
    expect(store.value).toBeNull();
    expect(onCompleted).toHaveBeenCalledTimes(1);
  });

  it('refuses to open the payments entry when it is not available', async () => {
    const { flow, api } = await atActivation();
    await flow.openPayments();
    expect(api.exit).not.toHaveBeenCalled();
    expect(flow.paymentsEntryOpened).toBe(false);
  });

  it('keeps the entry closed when the exit request fails', async () => {
    const api = fakeApi({ exit: failing('network') });
    const { flow } = await atActivation(api);
    await flow.activate();
    await flow.openPayments();
    expect(flow.paymentsEntryOpened).toBe(false);
    expect(flow.error).toContain('conectar');
  });

  it('ends the session, clears the store and starts over', async () => {
    const { flow, api, store } = await atActivation();
    await flow.activate();
    expect(store.value).toBe(ONBOARDING_ID);
    await flow.finish();
    expect(api.exit).toHaveBeenCalledWith(ONBOARDING_ID, 'END');
    expect(store.value).toBeNull();
    expect(flow.step).toBe('start');
    expect(flow.state).toBeNull();
    expect(flow.document).toBe('');
    expect(flow.notice).toContain('Terminaste');
  });

  it('stays at the exit when ending fails so it can be retried', async () => {
    const api = fakeApi({ exit: failing('unavailable') });
    const { flow, store } = await atActivation(api);
    await flow.activate();
    await flow.finish();
    expect(flow.step).toBe('exit');
    expect(store.value).toBe(ONBOARDING_ID);
    expect(flow.error).toContain('no está disponible');
  });

  it('ignores finish before the exit', async () => {
    const { flow, api } = await atTwoFactor();
    await flow.finish();
    expect(api.exit).not.toHaveBeenCalled();
  });
});

describe('OnboardingFlow completion signal', () => {
  it('fires once per onboarding even when the same state arrives again', async () => {
    const onCompleted = vi.fn();
    const { flow } = await atActivation(fakeApi(), memoryStore(), onCompleted);
    await flow.activate();
    await flow.openPayments();
    await flow.resume();
    expect(onCompleted).toHaveBeenCalledTimes(1);
    expect(onCompleted).toHaveBeenCalledWith(exitState);
  });

  it('does not fire for an approved result without a confirmed wallet, review or rejection', async () => {
    for (const result of [unconfirmedState, reviewState, rejectedState]) {
      const onCompleted = vi.fn();
      const { flow } = await atActivation(fakeApi({ activate: vi.fn(async () => result) }), memoryStore(), onCompleted);
      await flow.activate();
      expect(onCompleted).not.toHaveBeenCalled();
    }
  });

  it('fires when the refresh later confirms the wallet', async () => {
    const onCompleted = vi.fn();
    const api = fakeApi({ activate: vi.fn(async () => unconfirmedState), get: vi.fn(async () => exitState) });
    const { flow } = await atActivation(api, memoryStore(), onCompleted);
    await flow.activate();
    await flow.refresh();
    expect(onCompleted).toHaveBeenCalledTimes(1);
  });
});

describe('OnboardingFlow resume', () => {
  it('does nothing without a stored id', async () => {
    const api = fakeApi();
    const flow = new OnboardingFlow(api, memoryStore());
    await flow.resume();
    expect(api.get).not.toHaveBeenCalled();
    expect(flow.step).toBe('start');
  });

  it.each([
    ['DOCUMENT', documentState, 'document'],
    ['TWO_FACTOR', twoFactorState, 'two-factor'],
    ['ACTIVATION', activationState, 'activation'],
    ['EXIT', exitState, 'exit']
  ] as const)('resumes at the step the API reports (%s)', async (_label, result, step) => {
    const api = fakeApi({ get: vi.fn(async () => result) });
    const flow = new OnboardingFlow(api, memoryStore(ONBOARDING_ID));
    await flow.resume();
    expect(api.get).toHaveBeenCalledWith(ONBOARDING_ID);
    expect(flow.step).toBe(step);
    expect(flow.recoverableId).toBeNull();
  });

  it('clears the store when the API does not know the onboarding', async () => {
    const store = memoryStore(ONBOARDING_ID);
    const flow = new OnboardingFlow(fakeApi({ get: failing('not-found') }), store);
    await flow.resume();
    expect(store.value).toBeNull();
    expect(flow.recoverableId).toBeNull();
    expect(flow.step).toBe('start');
    expect(flow.error).toContain('No se encontró');
  });

  it('offers a retry and blocks a new registration after a recoverable failure', async () => {
    const get = vi.fn<OnboardingApi['get']>().mockRejectedValueOnce(new OnboardingApiError('network')).mockResolvedValueOnce(twoFactorState);
    const api = fakeApi({ get });
    const store = memoryStore(ONBOARDING_ID);
    const flow = new OnboardingFlow(api, store);
    await flow.resume();
    expect(flow.recoverableId).toBe(ONBOARDING_ID);
    expect(store.value).toBe(ONBOARDING_ID);
    expect(flow.error).toContain('conectar');

    await flow.start();
    expect(api.start).not.toHaveBeenCalled();
    expect(flow.error).toContain('registro en curso');
    flow.reset();
    expect(store.value).toBe(ONBOARDING_ID);

    await flow.resume();
    expect(flow.recoverableId).toBeNull();
    expect(flow.step).toBe('two-factor');
    expect(flow.error).toBe('');
  });

  it('does not resume while another request is running', async () => {
    const gate = deferred<Onboarding>();
    const api = fakeApi({ get: vi.fn(() => gate.promise) });
    const flow = new OnboardingFlow(api, memoryStore(ONBOARDING_ID));
    const first = flow.resume();
    await flow.resume();
    gate.resolve(twoFactorState);
    await first;
    expect(api.get).toHaveBeenCalledTimes(1);
  });

  it('forgets the session when a later request finds the onboarding gone', async () => {
    const api = fakeApi({ verifyTwoFactor: failing('not-found') });
    const { flow, store } = await atTwoFactor(api);
    flow.code = SECRET_CODE;
    await flow.verifyTwoFactor();
    expect(flow.step).toBe('start');
    expect(store.value).toBeNull();
    expect(flow.error).toContain('No se encontró');
  });
});

describe('OnboardingFlow privacy', () => {
  it('writes only the onboarding id to the store and never the document or the code', async () => {
    const store = memoryStore();
    const writeSpy = vi.spyOn(store, 'write');
    const { flow } = await atActivation(fakeApi(), store);
    await flow.activate();
    await flow.openPayments();
    await flow.finish();
    expect(writeSpy.mock.calls.length).toBeGreaterThan(0);
    for (const [value] of writeSpy.mock.calls) {
      expect(value).toBe(ONBOARDING_ID);
    }
    expect(JSON.stringify(store)).not.toContain(SECRET_DOCUMENT);
    expect(JSON.stringify(store)).not.toContain(SECRET_CODE);
  });

  it('keeps the error messages free of the document and the code', async () => {
    const api = fakeApi({ verifyTwoFactor: failing('two-factor-failed', { reason: 'INCORRECT' }) });
    const { flow } = await atTwoFactor(api);
    flow.code = SECRET_CODE;
    await flow.verifyTwoFactor();
    expect(flow.error).not.toContain(SECRET_CODE);
    expect(flow.error).not.toContain(SECRET_DOCUMENT);
    expect(flow.code).toBe('');
  });
});
