// SPDX-License-Identifier: MIT
import { createHash } from 'node:crypto';
import path from 'node:path';
import type { Skill } from '@opencode/schema/skill';

/** Reviewed, versioned teaching guidance (CC BY 4.0, original text). A skill is instruction
 * text only: it grants no tool, and nothing is discovered from workspaces or global folders. */
const CURATED = [
  { id: 'renulus.skill.evidence-appraisal.v1', name: 'evidence-appraisal',
    description: 'Appraise a nephrology guideline or study for a learner.',
    content: 'Appraise the source for a nephrology learner: state the question, population, intervention and comparator, ' +
      'the outcome that mattered, the size and certainty of the effect, and where the evidence stops. ' +
      'Name the guideline edition or study date. Separate what the source says from your own explanation. ' +
      'Never give patient-specific treatment instructions.' },
] as const;

export function curatedSkills(root: string): { info: Skill.Info; sha256: string }[] {
  return CURATED.map(skill => ({
    info: { id: skill.id, name: skill.name, description: skill.description, autoinvoke: false,
      path: path.resolve(root, 'curated-skills', skill.name + '.md'), content: skill.content } as unknown as Skill.Info,
    sha256: createHash('sha256').update(skill.content).digest('hex'),
  }));
}
