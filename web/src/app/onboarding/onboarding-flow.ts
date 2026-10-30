export type OnboardingStep = 'name' | 'review' | 'active';

export class OnboardingFlow {
  step: OnboardingStep = 'name';
  name = '';
  error = '';

  continue(): void {
    if (this.step !== 'name') {
      return;
    }

    const name = this.name.trim();
    if (name.length < 2 || name.length > 40) {
      this.error = 'Ingresa un nombre de demostración de 2 a 40 caracteres.';
      return;
    }

    this.name = name;
    this.error = '';
    this.step = 'review';
  }

  edit(): void {
    if (this.step === 'review') {
      this.step = 'name';
    }
  }

  activate(): void {
    if (this.step === 'review') {
      this.step = 'active';
    }
  }

  reset(): void {
    this.name = '';
    this.error = '';
    this.step = 'name';
  }
}
