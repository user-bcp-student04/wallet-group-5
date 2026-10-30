export interface PendingStore {
  read(): string | null;
  write(id: string): void;
  clear(): void;
}

// El almacenamiento puede estar bloqueado por el navegador; se ignora sin romper el flujo.
export function createPendingStore(storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>, key: string): PendingStore {
  return {
    read() {
      try {
        return storage.getItem(key);
      } catch {
        return null;
      }
    },
    write(id) {
      try {
        storage.setItem(key, id);
      } catch {
        // Sin persistencia: el flujo sigue funcionando hasta recargar.
      }
    },
    clear() {
      try {
        storage.removeItem(key);
      } catch {
        // Nada que limpiar.
      }
    }
  };
}
