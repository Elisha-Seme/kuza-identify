// API base: VITE_API_BASE if set, else the dev-server /api proxy (vite.config.ts).
const BASE = (import.meta.env.VITE_API_BASE as string) || "/api";

export interface DomainEntry {
  domain: string;
  raw_score: number;
  adjustment_factor: number;
  adjusted_score: number;
  evidence_text: string;
  scoring_model_version: string;
}

export interface Flag {
  id: string;
  rule_id: string;
  rule_description: string;
  fired_at: string;
}

export interface CandidateSignal {
  id: string;
  signal_type: string;
  evidence_text: string;
  confidence: string;
}

export interface FlaggedProfile {
  session_id: string;
  learner_id: string;
  learner_source: string;
  school_id: string;
  profile: DomainEntry[];
  flags: Flag[];
  nomination_amber_flags: number;
  candidate_signals: CandidateSignal[];
  existing_decision: string | null;
}

export async function listFlagged(): Promise<FlaggedProfile[]> {
  const r = await fetch(`${BASE}/panel/flagged`);
  if (!r.ok) throw new Error(`GET /panel/flagged -> ${r.status}`);
  return r.json();
}

export async function recordDecision(
  sessionId: string,
  reviewerId: string,
  decision: "advance" | "hold" | "decline",
  notes: string
): Promise<void> {
  const r = await fetch(`${BASE}/panel/sessions/${sessionId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer_id: reviewerId, decision, notes }),
  });
  if (!r.ok) throw new Error(`POST decision -> ${r.status}`);
}
