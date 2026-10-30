import { describe, expect, it } from 'vitest';
import { createPendingStore } from './pending-store';

describe('createPendingStore', () => {
  it('reads, writes and clears the stored id', () => {
    const data = new Map<string, string>();
    const store = createPendingStore(
      { getItem: (k) => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v), removeItem: (k) => void data.delete(k) },
      'key'
    );
    expect(store.read()).toBeNull();
    store.write('onb-1');
    expect(store.read()).toBe('onb-1');
    store.clear();
    expect(store.read()).toBeNull();
  });

  it('keeps working when the storage is blocked', () => {
    const blocked = () => { throw new Error('blocked'); };
    const store = createPendingStore({ getItem: blocked, setItem: blocked, removeItem: blocked }, 'key');
    expect(store.read()).toBeNull();
    expect(() => store.write('onb-1')).not.toThrow();
    expect(() => store.clear()).not.toThrow();
  });
});
