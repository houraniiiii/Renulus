import { Badge } from '../../ui';

export type ContentTrackId = 'general_nephrology' | 'esen_eph';
export interface TrackMetadata {
  id: ContentTrackId; title: string; available?: boolean; status?: string; reason?: string;
  version?: string; checked_on?: string; available_questions?: number;
  format_compatible_questions?: number; coverage_note?: string; exam_simulation_available?: boolean;
  aligned_objective_ids?: string[]; supporting_objective_ids?: string[];
  domains?: { id: string; label: string; status: string; available_questions: number;
    alignments: { id: string; scope_note: string; gaps: string[] }[] }[];
}
export interface StudySelection {
  track: ContentTrackId; title: string; status: string; message: string | null;
  topic_ids: string[]; objective_ids: Record<string, string[]>; mapping_version: string | null;
}
export const contentTrackId = (track: 'general' | 'eseneph'): ContentTrackId =>
  track === 'eseneph' ? 'esen_eph' : 'general_nephrology';

// The existing Flow section hierarchy keeps coverage beside the plan, with
// detailed gaps behind a native disclosure rather than a second focal panel.
export default function StudyTrack({ track, selection }: { track?: TrackMetadata; selection?: StudySelection }) {
  if (selection?.track !== 'esen_eph' && track?.id !== 'esen_eph') return <section className="study-track" aria-label="Study track coverage">
    <strong>{track?.title ?? 'General nephrology'}</strong>
    <p className="muted">Your saved topics guide automatic suggestions. You can explore every topic freely.</p>
    {selection?.message && <p>{selection.message}</p>}
  </section>;
  return <section className="study-track" aria-label="Study track coverage">
    <div className="activity-title"><strong>{track?.title ?? 'ESENeph preparation'}</strong>
      <Badge tone="warning">{track?.available ? 'Partial mapping' : 'Mapping unavailable'}</Badge></div>
    {track?.checked_on && <p className="muted">Mapping checked <time dateTime={track.checked_on}>{track.checked_on}</time>.</p>}
    {track?.available ? <p>{track.available_questions} original reviewed questions are linked to exam domains.
      {track.format_compatible_questions !== undefined && <> {track.format_compatible_questions} use the exam option format.</>}</p>
      : <p>{track?.reason ?? 'No active ESENeph programme metadata is available.'}</p>}
    <p>Exam simulation is unavailable. The partial mapping does not establish complete exam coverage or mastery.</p>
    {track?.coverage_note && <p className="muted">{track.coverage_note}</p>}
    {selection?.message && selection.message !== track?.reason && <p>{selection.message}</p>}
    {!!track?.domains?.length && <details className="study-track-details"><summary>Mapped domains and gaps</summary>
      <ul>{track.domains.map(domain => <li key={domain.id}><strong>{domain.label}</strong>
        <p>{domain.status === 'gap' ? 'Gap in the active content pack.' : `${domain.available_questions} linked reviewed questions; partial coverage.`}</p>
        {domain.alignments.map(alignment => <div key={alignment.id}>
          <p>{alignment.scope_note}</p>
          <ul>{alignment.gaps.map((gap, index) => <li key={index}>{gap}</li>)}</ul>
        </div>)}
      </li>)}</ul>
      {!!track.supporting_objective_ids?.length && <p>Curriculum-support objectives remain available through general topic study; they do not count as mapped exam domains.</p>}
    </details>}
  </section>;
}
