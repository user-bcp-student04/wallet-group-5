import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { OnboardingFlow } from './onboarding-flow';

@Component({
  selector: 'app-onboarding',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './onboarding.component.html',
  styleUrl: './onboarding.component.css'
})
export class OnboardingComponent {
  readonly flow = new OnboardingFlow();
}
