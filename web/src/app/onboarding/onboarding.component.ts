import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { OnboardingFlow, ONBOARDING_STEPS, SCENARIOS } from './onboarding-flow';
import { TWO_FACTOR_NOT_CONFIGURED_MESSAGE } from './onboarding-messages';
import { createPendingStore } from './pending-store';
import { HttpOnboardingApi } from './wallet-api';
import { ONBOARDING_API_BASE_URL, ONBOARDING_ID_STORAGE_KEY, TWO_FACTOR_CODE_LENGTH } from './wallet-config';

@Component({
  selector: 'app-onboarding',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './onboarding.component.html',
  styleUrl: './onboarding.component.css'
})
export class OnboardingComponent implements OnInit {
  readonly steps = ONBOARDING_STEPS;
  readonly scenarios = SCENARIOS;
  readonly codeLength = TWO_FACTOR_CODE_LENGTH;
  readonly twoFactorNotConfiguredMessage = TWO_FACTOR_NOT_CONFIGURED_MESSAGE;
  readonly flow = new OnboardingFlow(
    new HttpOnboardingApi(ONBOARDING_API_BASE_URL),
    createPendingStore(sessionStorage, ONBOARDING_ID_STORAGE_KEY)
  );

  constructor(private readonly changes: ChangeDetectorRef) {}

  ngOnInit(): void {
    void this.track(() => this.flow.resume());
  }

  start(): Promise<void> {
    return this.track(() => this.flow.start());
  }

  submitDocument(): Promise<void> {
    return this.track(() => this.flow.submitDocument());
  }

  verifyTwoFactor(): Promise<void> {
    return this.track(() => this.flow.verifyTwoFactor());
  }

  resendCode(): Promise<void> {
    return this.track(() => this.flow.resendCode());
  }

  activate(): Promise<void> {
    return this.track(() => this.flow.activate());
  }

  refresh(): Promise<void> {
    return this.track(() => this.flow.refresh());
  }

  openPayments(): Promise<void> {
    return this.track(() => this.flow.openPayments());
  }

  finish(): Promise<void> {
    return this.track(() => this.flow.finish());
  }

  retryRecovery(): Promise<void> {
    return this.track(() => this.flow.resume());
  }

  // La app no usa zone.js para detectar cambios: hay que repintar tras cada operación asíncrona.
  private async track(action: () => Promise<void>): Promise<void> {
    const pending = action();
    this.changes.markForCheck();
    try {
      await pending;
    } finally {
      this.changes.markForCheck();
    }
  }
}
