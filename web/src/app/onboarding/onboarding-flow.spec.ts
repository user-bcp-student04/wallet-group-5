import { describe, expect, it } from 'vitest';
import { OnboardingFlow } from './onboarding-flow';

describe('OnboardingFlow', () => {
  it('starts on the name step without an active wallet', () => {
    const flow = new OnboardingFlow();
    expect(flow.step).toBe('name');
    expect(flow.name).toBe('');
  });

  it.each(['', ' ', 'a', 'x'.repeat(41)])('blocks invalid name %s', (name) => {
    const flow = new OnboardingFlow();
    flow.name = name;
    flow.continue();
    expect(flow.step).toBe('name');
    expect(flow.error).toContain('2 a 40');
  });

  it.each(['Al', 'x'.repeat(40)])('accepts and normalizes valid name %s', (name) => {
    const flow = new OnboardingFlow();
    flow.name = ` ${name} `;
    flow.continue();
    expect(flow.step).toBe('review');
    expect(flow.name).toBe(name);
    expect(flow.error).toBe('');
  });

  it('only activates after review and allows editing', () => {
    const flow = new OnboardingFlow();
    flow.activate();
    expect(flow.step).toBe('name');
    flow.name = 'Alex';
    flow.continue();
    flow.edit();
    expect(flow.step).toBe('name');
    expect(flow.name).toBe('Alex');
    flow.continue();
    flow.activate();
    expect(flow.step).toBe('active');
    flow.edit();
    flow.continue();
    expect(flow.step).toBe('active');
  });

  it('clears the simulated state when restarted', () => {
    const flow = new OnboardingFlow();
    flow.name = 'Alex';
    flow.continue();
    flow.activate();
    flow.reset();
    expect(flow.step).toBe('name');
    expect(flow.name).toBe('');
    expect(flow.error).toBe('');
  });
});
