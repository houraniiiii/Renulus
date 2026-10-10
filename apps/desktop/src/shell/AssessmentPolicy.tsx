import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, isCancelled } from '../platform/api';
import type { AssessmentPolicy } from '../platform/designC';

interface PolicyState { policy: AssessmentPolicy | null; error: boolean; refresh: () => void }
const PolicyContext = createContext<PolicyState | null>(null);
export function AssessmentPolicyProvider({ children }: { children: ReactNode }) {
  const [policy, setPolicy] = useState<AssessmentPolicy | null>(null);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  const refresh = () => setRevision(value => value + 1);
  useEffect(() => {
    window.addEventListener('renulus:assessment-policy', refresh);
    return () => window.removeEventListener('renulus:assessment-policy', refresh);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function read() {
      try {
        const next = await api<AssessmentPolicy>('/assessment/policy', { signal: controller.signal });
        if (!Number.isSafeInteger(next.revision) || typeof next.assistance_allowed !== 'boolean' || !(next.active_test_id === null || typeof next.active_test_id === 'string')) throw new Error('Invalid policy');
        if (!controller.signal.aborted) { setPolicy(next); setError(false); }
      } catch (failure) {
        if (!controller.signal.aborted && !isCancelled(failure)) { setPolicy(null); setError(true); }
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(() => { void read(); }, 1000);
      }
    }
    void read();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [revision]);
  return <PolicyContext.Provider value={{ policy, error, refresh }}>{children}</PolicyContext.Provider>;
}
export function useAssessmentPolicy() {
  const value = useContext(PolicyContext);
  if (!value) throw new Error('Assessment policy requires the Renulus shell');
  return value;
}
