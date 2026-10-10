/** Shell-owned memory only. It survives a policy gate, never a fresh navigation. */
export interface VolatileHomeDraft { text: string; intent: 'explain' | 'case' | 'practice' }
