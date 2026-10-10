import { useCallback, useEffect, useRef, useState } from 'react';
import { isCancelled } from '../../platform/api';
import { readNightly } from './api';
import { isActive, type NightlyState } from './types';

/** Reads only; the app-running backend owns every scheduling decision. */
export function useNightlyStatus() {
  const [data, setData] = useState<NightlyState>();
  const [error, setError] = useState<unknown>();
  const [version, setVersion] = useState(0);
  const previous = useRef<NightlyState | undefined>(undefined);
  const refresh = useCallback(() => setVersion(value => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    function schedule(state: NightlyState | undefined) {
      if (!controller.signal.aborted && state && (state.preferences.enabled || isActive(state.last_job)))
        timer = setTimeout(refresh, isActive(state.last_job) ? 5_000 : 30_000);
    }
    void readNightly(controller.signal).then(value => {
      if (controller.signal.aborted) return;
      previous.current = value; setData(value); setError(undefined); schedule(value);
    }).catch(failure => {
      if (!controller.signal.aborted && !isCancelled(failure)) { setError(failure); schedule(previous.current); }
    });
    return () => { controller.abort(); clearTimeout(timer); };
  }, [version, refresh]);
  useEffect(() => {
    window.addEventListener('renulus:records-changed', refresh);
    window.addEventListener('renulus:assessment-policy', refresh);
    return () => {
      window.removeEventListener('renulus:records-changed', refresh);
      window.removeEventListener('renulus:assessment-policy', refresh);
    };
  }, [refresh]);
  return { data, error, refresh };
}
