import { describe, expect, it, vi } from 'vitest';
import { HttpOnboardingApi, OnboardingApiError, OnboardingApiErrorKind } from './wallet-api';

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

const wallet = { id: 'wal-1', status: 'ACTIVE', balance: 0, reserved: 0, available: 0, currency: 'PEN' };
const states = { registration: 'PERSISTED', verification: 'VERIFIED', activation: 'ACTIVE', provider: 'ACTIVE' };
const activeBody = {
  onboardingId: 'onb 1',
  step: 'EXIT',
  states,
  twoFactorAvailable: true,
  wallet,
  paymentsEntryAvailable: true
};

async function failure(promise: Promise<unknown>): Promise<OnboardingApiError> {
  try {
    await promise;
  } catch (error) {
    return error as OnboardingApiError;
  }
  throw new Error('Expected the request to fail');
}

function apiReplying(status: number, body: unknown) {
  const fetchFn = vi.fn(async (_url: string, _init?: RequestInit) => json(status, body));
  return { api: new HttpOnboardingApi('http://api', fetchFn), fetchFn };
}

function lastCall(fetchFn: ReturnType<typeof vi.fn>): [string, RequestInit] {
  return fetchFn.mock.calls[fetchFn.mock.calls.length - 1] as unknown as [string, RequestInit];
}

describe('HttpOnboardingApi requests', () => {
  it('starts without a body and parses the full state', async () => {
    const { api, fetchFn } = apiReplying(201, activeBody);
    expect(await api.start()).toEqual(activeBody);
    const [url, init] = lastCall(fetchFn);
    expect(url).toBe('http://api/api/onboarding');
    expect(init.method).toBe('POST');
    expect(init.body).toBeUndefined();
  });

  it('gets by identifier, encoding it in the path', async () => {
    const { api, fetchFn } = apiReplying(200, activeBody);
    await api.get('onb 1/../x');
    const [url, init] = lastCall(fetchFn);
    expect(url).toBe('http://api/api/onboarding/onb%201%2F..%2Fx');
    expect(init.method).toBe('GET');
  });

  it('submits the document with PUT and the documented body', async () => {
    const { api, fetchFn } = apiReplying(200, activeBody);
    await api.submitDocument('onb-1', 'TEST-001', 'MANUAL_REVIEW');
    const [url, init] = lastCall(fetchFn);
    expect(url).toBe('http://api/api/onboarding/onb-1/document');
    expect(init.method).toBe('PUT');
    expect(JSON.parse(init.body as string)).toEqual({ documentType: 'TEST', document: 'TEST-001', scenario: 'MANUAL_REVIEW' });
  });

  it('requests a challenge and activates without a body', async () => {
    const { api, fetchFn } = apiReplying(200, activeBody);
    await api.requestChallenge('onb-1');
    expect(lastCall(fetchFn)[0]).toBe('http://api/api/onboarding/onb-1/challenge');
    expect(lastCall(fetchFn)[1].body).toBeUndefined();
    await api.activate('onb-1');
    expect(lastCall(fetchFn)[0]).toBe('http://api/api/onboarding/onb-1/activate');
    expect(lastCall(fetchFn)[1].method).toBe('POST');
  });

  it('verifies the second factor with the code in the body', async () => {
    const { api, fetchFn } = apiReplying(200, activeBody);
    await api.verifyTwoFactor('onb-1', '123456');
    const [url, init] = lastCall(fetchFn);
    expect(url).toBe('http://api/api/onboarding/onb-1/two-factor');
    expect(JSON.parse(init.body as string)).toEqual({ code: '123456' });
  });

  it.each(['CONTINUE', 'END'] as const)('exits with action %s', async (action) => {
    const { api, fetchFn } = apiReplying(200, activeBody);
    await api.exit('onb-1', action);
    const [url, init] = lastCall(fetchFn);
    expect(url).toBe('http://api/api/onboarding/onb-1/exit');
    expect(JSON.parse(init.body as string)).toEqual({ action });
  });
});

describe('HttpOnboardingApi parsing', () => {
  it('accepts a missing or null wallet and a null provider', async () => {
    const pending = { ...activeBody, wallet: undefined, states: { ...states, provider: null }, paymentsEntryAvailable: false };
    expect((await apiReplying(200, pending).api.get('k')).wallet).toBeNull();
    expect((await apiReplying(200, { ...pending, wallet: null }).api.get('k')).states.provider).toBeNull();
  });

  it.each([
    { onboardingId: 'k' },
    { ...activeBody, onboardingId: 5 },
    { ...activeBody, step: 'DONE' },
    { ...activeBody, twoFactorAvailable: 'yes' },
    { ...activeBody, paymentsEntryAvailable: undefined },
    { ...activeBody, states: undefined },
    { ...activeBody, states: { ...states, registration: 'OTHER' } },
    { ...activeBody, states: { ...states, verification: 'OTHER' } },
    { ...activeBody, states: { ...states, activation: 'OTHER' } },
    { ...activeBody, states: { ...states, provider: 'OTHER' } },
    { ...activeBody, states: { ...states, provider: undefined } },
    { ...activeBody, wallet: { id: 'w' } },
    { ...activeBody, wallet: { ...wallet, balance: '0' } },
    null,
    'text'
  ])('rejects an unexpected payload %j', async (body) => {
    expect((await failure(apiReplying(200, body).api.get('k'))).kind).toBe('unexpected');
  });
});

describe('HttpOnboardingApi errors', () => {
  const cases: Array<[number, unknown, OnboardingApiErrorKind]> = [
    [400, { detail: { error: 'TWO_FACTOR_FAILED', reason: 'INCORRECT' } }, 'two-factor-failed'],
    [400, { detail: { error: 'OTHER' } }, 'validation'],
    [413, { detail: { error: 'CODE' } }, 'validation'],
    [422, { detail: [{ loc: ['body'], msg: 'x', type: 'y' }] }, 'validation'],
    [403, { detail: { error: 'TWO_FACTOR_REQUIRED' } }, 'two-factor-required'],
    [403, { detail: { error: 'OTHER' } }, 'unexpected'],
    [404, { detail: { error: 'NOT_FOUND' } }, 'not-found'],
    [409, { detail: { error: 'INVALID_STEP' } }, 'invalid-step'],
    [409, { detail: { error: 'REGISTRATION_UNAVAILABLE', message: 'm' } }, 'registration-unavailable'],
    [409, { detail: { error: 'OTHER' } }, 'unexpected'],
    [409, { detail: [{ msg: 'x' }] }, 'unexpected'],
    [429, { detail: { error: 'TWO_FACTOR_LOCKED', retryAfterSeconds: 30 } }, 'two-factor-locked'],
    [429, { detail: { error: 'TWO_FACTOR_LIMIT' } }, 'two-factor-limit'],
    [429, { detail: { error: 'PROVIDER_LIMIT_REACHED' } }, 'limit'],
    [502, { detail: { error: 'PROVIDER_ERROR' } }, 'unavailable'],
    [503, { detail: { error: 'KYC_UNAVAILABLE' } }, 'unavailable'],
    [503, { detail: { error: 'TWO_FACTOR_UNAVAILABLE' } }, 'two-factor-unavailable'],
    [504, { detail: { error: 'KYC_RESULT_UNKNOWN' } }, 'unknown-result'],
    [500, { detail: { error: 'CODE' } }, 'unexpected']
  ];

  it.each(cases)('maps HTTP %i %j to %s', async (status, body, kind) => {
    const error = await failure(apiReplying(status, body).api.activate('k'));
    expect(error).toBeInstanceOf(OnboardingApiError);
    expect(error.kind).toBe(kind);
  });

  it.each([
    ['INCORRECT', 'INCORRECT'],
    ['EXPIRED', 'EXPIRED'],
    ['OTHER', undefined]
  ])('keeps the failure reason %s of a rejected code', async (reason, expected) => {
    const api = apiReplying(400, { detail: { error: 'TWO_FACTOR_FAILED', reason } }).api;
    expect((await failure(api.verifyTwoFactor('k', '123456'))).reason).toBe(expected);
  });

  it.each([
    [30, 30],
    [0, undefined],
    ['30', undefined]
  ])('keeps retryAfterSeconds %j of a lock as %j', async (retryAfterSeconds, expected) => {
    const api = apiReplying(429, { detail: { error: 'TWO_FACTOR_LOCKED', retryAfterSeconds } }).api;
    expect((await failure(api.verifyTwoFactor('k', '123456'))).retryAfterSeconds).toBe(expected);
  });

  it('keeps only the neutral message of REGISTRATION_UNAVAILABLE', async () => {
    const neutral = apiReplying(409, { detail: { error: 'REGISTRATION_UNAVAILABLE', message: 'No se pudo completar.' } }).api;
    const error = await failure(neutral.activate('k'));
    expect(error.message).toBe('No se pudo completar.');
    const blank = apiReplying(409, { detail: { error: 'REGISTRATION_UNAVAILABLE', message: '  ' } }).api;
    expect((await failure(blank.activate('k'))).message).toBe('registration-unavailable');
    const other = apiReplying(409, { detail: { error: 'INVALID_STEP', message: 'secret' } }).api;
    expect((await failure(other.activate('k'))).message).toBe('invalid-step');
  });

  it('never puts the document or the code in the error', async () => {
    const api = apiReplying(422, { detail: [{ msg: 'bad TEST-SECRET 654321' }] }).api;
    const documentError = await failure(api.submitDocument('k', 'TEST-SECRET', 'APPROVED'));
    const codeError = await failure(api.verifyTwoFactor('k', '654321'));
    expect(documentError.message).not.toContain('TEST-SECRET');
    expect(codeError.message).not.toContain('654321');
  });

  it('tolerates bodies without JSON', async () => {
    const api = new HttpOnboardingApi('http://api', async () => new Response('bad gateway', { status: 502 }));
    expect((await failure(api.get('k'))).kind).toBe('unavailable');
  });

  it('reports a network failure', async () => {
    const api = new HttpOnboardingApi('http://api', async () => { throw new TypeError('Failed to fetch'); });
    expect((await failure(api.get('k'))).kind).toBe('network');
  });

  it('aborts a request whose body never finishes arriving', async () => {
    vi.useFakeTimers();
    try {
      const fetchFn = vi.fn(async (_url: string, init?: RequestInit) => ({
        ok: true,
        status: 200,
        json: () => new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
        })
      }) as unknown as Response);
      const pending = failure(new HttpOnboardingApi('http://api', fetchFn).get('k'));
      await vi.advanceTimersByTimeAsync(15000);
      expect((await pending).kind).toBe('network');
    } finally {
      vi.useRealTimers();
    }
  });

  it('aborts a request that exceeds the timeout', async () => {
    vi.useFakeTimers();
    try {
      const fetchFn = vi.fn((_url: string, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
      }));
      const pending = failure(new HttpOnboardingApi('http://api', fetchFn).get('k'));
      await vi.advanceTimersByTimeAsync(15000);
      expect((await pending).kind).toBe('network');
    } finally {
      vi.useRealTimers();
    }
  });
});
