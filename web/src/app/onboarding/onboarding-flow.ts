import {
  describeError,
  FlowAction,
  INVALID_CODE_MESSAGE,
  INVALID_DOCUMENT_MESSAGE,
  NEW_CODE_SENT_MESSAGE,
  PENDING_BLOCKS_NEW_REGISTRATION_MESSAGE,
  SESSION_FINISHED_MESSAGE,
  TWO_FACTOR_NOT_CONFIGURED_MESSAGE
} from './onboarding-messages';
import { PendingStore } from './pending-store';
import {
  Onboarding,
  OnboardingApi,
  OnboardingApiError,
  OnboardingApiErrorKind,
  OnboardingApiStep,
  OnboardingScenario,
  Wallet
} from './wallet-api';
import { TWO_FACTOR_CODE_PATTERN } from './wallet-config';

export type OnboardingStep = 'start' | 'document' | 'two-factor' | 'activation' | 'exit';
export type ActivationOutcome = 'ready' | 'unconfirmed' | 'in-review' | 'rejected';

export const DOCUMENT_TYPE = 'TEST';
export const DOCUMENT_PREFIX = 'TEST-';
export const MAX_DOCUMENT_LENGTH = 200;
export const DOCUMENT_NOT_REMEMBERED_LABEL = 'Registrado (no se conserva al recargar la página)';

export const ONBOARDING_STEPS: ReadonlyArray<{ step: OnboardingStep; label: string }> = [
  { step: 'start', label: 'Inicio' },
  { step: 'document', label: 'Documento' },
  { step: 'two-factor', label: 'Doble factor' },
  { step: 'activation', label: 'Activación' },
  { step: 'exit', label: 'Salida' }
];

export const SCENARIOS: ReadonlyArray<{ value: OnboardingScenario; label: string }> = [
  { value: 'APPROVED', label: 'Aprobado' },
  { value: 'MANUAL_REVIEW', label: 'Revisión manual' },
  { value: 'REJECTED', label: 'Rechazado' },
  { value: 'UNAVAILABLE', label: 'Servicio no disponible' }
];

const STEP_BY_API_STEP: Record<OnboardingApiStep, OnboardingStep> = {
  DOCUMENT: 'document',
  TWO_FACTOR: 'two-factor',
  ACTIVATION: 'activation',
  EXIT: 'exit'
};

// Errores tras los cuales el estado local puede estar desfasado y se vuelve a pedir a la API.
const RESYNC_KINDS: readonly OnboardingApiErrorKind[] = ['invalid-step', 'two-factor-required'];
const SAVED_DOCUMENT_KINDS: readonly OnboardingApiErrorKind[] = ['two-factor-locked', 'two-factor-limit'];

function isValidDocument(document: string): boolean {
  return (
    document.startsWith(DOCUMENT_PREFIX) && document.length > DOCUMENT_PREFIX.length && document.length <= MAX_DOCUMENT_LENGTH
  );
}

function kindOf(error: unknown): OnboardingApiErrorKind {
  return error instanceof OnboardingApiError ? error.kind : 'unexpected';
}

// La API es la fuente única del paso; aquí solo se traduce y se guardan los datos en memoria.
// El documento y el código viven únicamente en esta instancia: el store recibe solo el onboardingId.
export class OnboardingFlow {
  readonly documentType = DOCUMENT_TYPE;
  document = '';
  scenario: OnboardingScenario = 'APPROVED';
  code = '';
  error = '';
  notice = '';
  busy = false;
  state: Onboarding | null = null;
  paymentsEntryOpened = false;

  // Identificador de un registro en curso que no se pudo consultar al reanudar.
  recoverableId: string | null = null;

  private editingDocument = false;
  private completedFor: string | null = null;

  constructor(
    private readonly api: OnboardingApi,
    private readonly pending: PendingStore,
    private readonly onCompleted: (state: Onboarding) => void = () => undefined
  ) {}

  get step(): OnboardingStep {
    if (this.state === null) {
      return 'start';
    }
    return this.editingDocument ? 'document' : STEP_BY_API_STEP[this.state.step];
  }

  // Solo una wallet activa y confirmada por la API cuenta como confirmada.
  get wallet(): Wallet | null {
    const wallet = this.state?.wallet ?? null;
    return wallet !== null && wallet.status === 'ACTIVE' && this.state?.states.activation === 'ACTIVE' ? wallet : null;
  }

  get activationOutcome(): ActivationOutcome {
    const provider = this.state?.states.provider ?? null;
    if (provider === 'REJECTED') {
      return 'rejected';
    }
    if (provider === 'PENDING') {
      return 'in-review';
    }
    return provider === 'ACTIVE' ? 'unconfirmed' : 'ready';
  }

  // Aprobada o en revisión sin wallet confirmada: hay que volver a consultar antes de dar el alta por completa.
  get needsFollowUp(): boolean {
    return this.step === 'activation' && (this.activationOutcome === 'in-review' || this.activationOutcome === 'unconfirmed');
  }

  get twoFactorBlocked(): boolean {
    return this.state !== null && !this.state.twoFactorAvailable;
  }

  // Editando un documento ya enviado: solo entonces se ofrece volver al doble factor sin cambiarlo.
  get isEditingDocument(): boolean {
    return this.editingDocument;
  }

  get canEditDocument(): boolean {
    return this.step === 'two-factor' && !this.busy;
  }

  get paymentsEntryAvailable(): boolean {
    return this.step === 'exit' && this.state?.paymentsEntryAvailable === true && this.wallet !== null;
  }

  get documentSummary(): string {
    return this.document || DOCUMENT_NOT_REMEMBERED_LABEL;
  }

  async start(): Promise<void> {
    if (this.step !== 'start' || this.busy) {
      return;
    }
    if (this.recoverableId !== null) {
      this.error = PENDING_BLOCKS_NEW_REGISTRATION_MESSAGE;
      return;
    }
    await this.run('start', () => this.api.start());
  }

  async submitDocument(): Promise<void> {
    const id = this.state?.onboardingId;
    if (this.step !== 'document' || this.busy || id === undefined) {
      return;
    }

    const document = this.document.trim();
    this.error = '';
    if (!isValidDocument(document)) {
      this.error = INVALID_DOCUMENT_MESSAGE;
      return;
    }

    this.document = document;
    const failure = await this.run('document', () => this.api.submitDocument(id, document, this.scenario));
    if (failure === null) {
      this.code = '';
    }
  }

  editDocument(): void {
    if (this.canEditDocument) {
      this.error = '';
      this.notice = '';
      this.editingDocument = true;
    }
  }

  cancelEditDocument(): void {
    if (this.editingDocument && !this.busy) {
      this.error = '';
      this.editingDocument = false;
    }
  }

  async verifyTwoFactor(): Promise<void> {
    const id = this.state?.onboardingId;
    if (this.step !== 'two-factor' || this.busy || id === undefined) {
      return;
    }
    this.error = '';
    this.notice = '';
    if (this.twoFactorBlocked) {
      this.error = TWO_FACTOR_NOT_CONFIGURED_MESSAGE;
      return;
    }

    const code = this.code.trim();
    if (!TWO_FACTOR_CODE_PATTERN.test(code)) {
      this.error = INVALID_CODE_MESSAGE;
      return;
    }

    await this.run('verify', () => this.api.verifyTwoFactor(id, code));
    this.code = '';
  }

  async resendCode(): Promise<void> {
    const id = this.state?.onboardingId;
    if (this.step !== 'two-factor' || this.busy || id === undefined) {
      return;
    }
    if (this.twoFactorBlocked) {
      this.error = TWO_FACTOR_NOT_CONFIGURED_MESSAGE;
      return;
    }

    const failure = await this.run('challenge', () => this.api.requestChallenge(id));
    if (failure === null) {
      this.code = '';
      this.notice = NEW_CODE_SENT_MESSAGE;
    }
  }

  // Una confirmación envía una sola solicitud; la API aplica además la regla de cuenta única.
  async activate(): Promise<void> {
    const id = this.state?.onboardingId;
    if (this.step !== 'activation' || this.activationOutcome !== 'ready' || this.busy || id === undefined) {
      return;
    }
    await this.run('activate', () => this.api.activate(id));
  }

  async refresh(): Promise<void> {
    const id = this.state?.onboardingId;
    if (!this.needsFollowUp || this.busy || id === undefined) {
      return;
    }
    await this.run('load', () => this.api.get(id));
  }

  // Abre el punto de entrada a pagos de bajo monto; no inicia ningún pago.
  async openPayments(): Promise<void> {
    const id = this.state?.onboardingId;
    if (!this.paymentsEntryAvailable || this.busy || id === undefined) {
      return;
    }
    const failure = await this.run('exit', () => this.api.exit(id, 'CONTINUE'));
    if (failure === null) {
      this.paymentsEntryOpened = true;
      this.pending.clear();
    }
  }

  async finish(): Promise<void> {
    const id = this.state?.onboardingId;
    if (this.step !== 'exit' || this.busy || id === undefined) {
      return;
    }
    const failure = await this.run('exit', () => this.api.exit(id, 'END'));
    if (failure === null) {
      this.clearSession();
      this.notice = SESSION_FINISHED_MESSAGE;
    }
  }

  async resume(): Promise<void> {
    const id = this.pending.read();
    if (!id || this.busy) {
      return;
    }
    const failure = await this.run('load', () => this.api.get(id));
    // Si no hay nada que mostrar, el registro sigue pendiente de consultar: se ofrece reintentar.
    if (failure !== null && failure !== 'not-found' && this.state === null) {
      this.recoverableId = id;
    }
  }

  reset(): void {
    if (this.busy || this.recoverableId !== null || this.needsFollowUp) {
      return;
    }
    this.clearSession();
  }

  // Devuelve el tipo de fallo, o null si la operación terminó bien.
  private async run(action: FlowAction, operation: () => Promise<Onboarding>): Promise<OnboardingApiErrorKind | null> {
    this.busy = true;
    this.error = '';
    this.notice = '';
    try {
      this.apply(await operation());
      return null;
    } catch (error) {
      await this.fail(error, action);
      return kindOf(error);
    } finally {
      this.busy = false;
    }
  }

  private async fail(error: unknown, action: FlowAction): Promise<void> {
    const kind = kindOf(error);
    if (kind === 'not-found') {
      this.clearSession();
    } else if (RESYNC_KINDS.includes(kind) || (action === 'document' && SAVED_DOCUMENT_KINDS.includes(kind))) {
      await this.resync();
    }
    this.error = describeError(error, action);
  }

  // El estado de la API manda; si no se puede consultar, se conserva lo que ya se mostraba.
  private async resync(): Promise<void> {
    const id = this.state?.onboardingId;
    if (id === undefined) {
      return;
    }
    try {
      this.apply(await this.api.get(id));
    } catch {
      // El mensaje del error original sigue siendo el que se muestra.
    }
  }

  private apply(state: Onboarding): void {
    this.state = state;
    this.editingDocument = false;
    this.recoverableId = null;
    this.pending.write(state.onboardingId);

    if (this.wallet !== null && this.completedFor !== state.onboardingId) {
      this.completedFor = state.onboardingId;
      this.onCompleted(state);
    }
  }

  private clearSession(): void {
    this.pending.clear();
    this.state = null;
    this.recoverableId = null;
    this.editingDocument = false;
    this.paymentsEntryOpened = false;
    this.document = '';
    this.scenario = 'APPROVED';
    this.code = '';
    this.error = '';
    this.notice = '';
  }
}
