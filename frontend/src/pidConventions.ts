import { useEffect, useState } from 'react';
import { api } from './api';
import type { PidConventions, PidService } from './types';

export function usePidConventions() {
  const [conventions, setConventions] = useState<PidConventions | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    void api<PidConventions>('/pid/conventions', 'GET', undefined, controller.signal)
      .then(value => { if (!controller.signal.aborted) { setConventions(value); setError(''); } })
      .catch(error => { if (!controller.signal.aborted) setError(error instanceof Error ? error.message : String(error)); });
    return () => controller.abort();
  }, []);
  return { conventions, error };
}

export const serviceDefinition = (conventions: PidConventions | null, id?: PidService) => conventions?.services.find(service => service.id === (id ?? 'unspecified'));
export const serviceCode = (conventions: PidConventions | null, id?: PidService) => !id || id === 'unspecified' ? '' : serviceDefinition(conventions, id)?.code ?? id;
