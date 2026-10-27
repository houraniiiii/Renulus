// SPDX-License-Identifier: MIT
// Public programme coverage derived from exact active pins (port of content/programmes.py).
// No learner records or model output enter this module.
import type { ObjectValue } from '../assessment/contracts.ts';

const list = (value: unknown): ObjectValue[] => Array.isArray(value) ? value : [];
const pinKey = (pin: ObjectValue) => pin.id + '@' + pin.version;

export function mappedQuestionPins(manifest: ObjectValue | null, track: string): Set<string> {
  const programme = list(manifest?.programme_mappings).find(p => p.id === track);
  return new Set(programme ? list(programme.alignments).filter(row => row.relation === 'exam_domain').flatMap(row => list(row.questions).map(pinKey)) : []);
}
function activeAlignment(row: ObjectValue, selected: Map<string, ObjectValue>, cases: Map<string, ObjectValue>) {
  const questions = list(row.questions).filter(p => selected.has(pinKey(p))), caseRows = list(row.cases).filter(p => cases.has(pinKey(p)));
  const supported = new Set([...questions.flatMap(p => selected.get(pinKey(p))!.objective_ids), ...caseRows.flatMap(p => cases.get(pinKey(p))!.objective_ids)]);
  const status = questions.length || caseRows.length ? (row.relation === 'curriculum_support' ? 'supporting' : 'partial') : 'gap';
  return { ...row, questions, cases: caseRows, objective_ids: [...new Set(row.objective_ids as string[])].filter(o => supported.has(o)).sort(), status };
}
const unavailable = (reason: string) => ({ id: 'esen_eph', title: 'ESENeph preparation', available: false, status: 'not_formally_mapped', reason, exam_simulation_available: false });
export function programmeMetadata(manifest: ObjectValue | null, topics: ObjectValue[], cases: ObjectValue[], allQuestions: ObjectValue[]): ObjectValue[] {
  const questions = allQuestions.filter(q => q.usage === 'assessment_reserved');
  const general = { id: 'general_nephrology', title: 'General nephrology', available: questions.length > 0, available_families: new Set(questions.map(q => q.family_id)).size };
  if (!manifest) return [general, unavailable('No active content pack')];
  const programme = list(manifest.programme_mappings).find(p => p.id === 'esen_eph');
  if (!programme) return [general, unavailable('The active pack has no formal mapping')];
  const selected = new Map(questions.map(q => [pinKey(q), q])), casePins = new Map(cases.map(c => [pinKey(c), c]));
  const mapped = [...mappedQuestionPins(manifest, 'esen_eph')].filter(key => selected.has(key));
  const allObjectives = new Set(topics.flatMap(t => list(t.objectives).map(o => o.id as string)));
  const examObjectives = new Set<string>(), mappedCases = new Set<string>();
  const domains = list(programme.domains).map(domain => {
    const rows = list(programme.alignments).filter(r => r.domain_id === domain.id);
    const pins = new Set(rows.flatMap(r => list(r.questions).map(pinKey)).filter(key => selected.has(key)));
    const families = new Set([...pins].map(key => selected.get(key)!.family_id));
    const activeRows = rows.map(row => {
      const active = activeAlignment(row, selected, casePins);
      active.objective_ids.forEach((o: string) => examObjectives.add(o)); active.cases.forEach(p => mappedCases.add(pinKey(p)));
      return active;
    });
    return { ...domain, available_questions: pins.size, available_families: families.size,
      family_shortfall: Math.max(0, domain.indicative_questions - families.size),
      status: activeRows.some(r => r.status === 'partial') ? 'partial' : 'gap', alignments: activeRows };
  });
  const supporting = list(programme.alignments).filter(r => r.relation === 'curriculum_support').map(row => activeAlignment(row, selected, casePins));
  const supportObjectives = new Set(supporting.flatMap(row => row.objective_ids as string[]));
  const reviewCounts = (status: string) => mapped.filter(key => selected.get(key)!.review?.status === status).length;
  const options: Record<string, number> = {};
  for (const key of mapped) { const n = String(list(selected.get(key)!.options).length); options[n] = (options[n] ?? 0) + 1; }
  const metadata: ObjectValue = {};
  for (const k of ['id', 'version', 'title', 'checked_on', 'status', 'method', 'reviewer_kind', 'independent_human_review', 'official_endorsement', 'exam_simulation_available', 'evidence', 'exam']) metadata[k] = programme[k];
  Object.assign(metadata, {
    available: mapped.length > 0, pack: { id: manifest.id, version: manifest.version }, available_questions: mapped.length,
    available_families: new Set(mapped.map(key => selected.get(key)!.family_id)).size, unmapped_questions: selected.size - mapped.length,
    available_cases: mappedCases.size, aligned_objective_ids: [...examObjectives].sort(), supporting_objective_ids: [...supportObjectives].sort(),
    unaligned_objective_ids: [...allObjectives].filter(o => !examObjectives.has(o) && !supportObjectives.has(o)).sort(), supporting_alignments: supporting,
    excluded_questions: list(programme.excluded_questions).filter(pin => selected.has(pinKey(pin))),
    option_count_distribution: Object.fromEntries(Object.entries(options).sort(([a], [b]) => Number(a) - Number(b))),
    format_compatible_questions: mapped.filter(key => list(selected.get(key)!.options).length === programme.exam.options_per_question).length,
    review_counts: { assistant_reviewed: reviewCounts('assistant_reviewed'), human_reviewed: reviewCounts('human_reviewed') }, domains,
    coverage_note: 'Partial assistant mapping of original learning content. Domain weights are indicative; item counts and objective links do not establish full depth, clinician review, mastery or an exam simulation. Generated practice is excluded.',
  });
  if (!mapped.length) metadata.reason = 'No eligible active reviewed questions remain in the mapped track';
  return [general, metadata];
}
