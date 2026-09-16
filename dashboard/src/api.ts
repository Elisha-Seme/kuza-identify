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

export interface ScreeningItem {
  id: string;
  domain: string;
  difficulty: number;
  prompt: { en: string; sw: string };
}

export async function listItems(): Promise<ScreeningItem[]> {
  const r = await fetch(`${BASE}/screening/items`);
  if (!r.ok) throw new Error(`GET /screening/items -> ${r.status}`);
  return r.json();
}

export interface SchoolRow {
  id: string;
  name: string;
  tier: string;
}

export async function listSchools(): Promise<SchoolRow[]> {
  const r = await fetch(`${BASE}/nomination/schools`);
  if (!r.ok) throw new Error(`GET /nomination/schools -> ${r.status}`);
  return r.json();
}

export interface ChecklistItem {
  key: string;
  prompt_en: string;
  prompt_sw: string;
  amber_flag: boolean;
}

export async function getNominationForm(): Promise<ChecklistItem[]> {
  const r = await fetch(`${BASE}/nomination/form`);
  if (!r.ok) throw new Error(`GET /nomination/form -> ${r.status}`);
  return r.json();
}

export async function submitNomination(body: {
  school_id: string;
  nominator_role: "teacher" | "parent";
  checklist_responses: Record<string, boolean>;
  gender?: string;
  cohort_id?: string;
  guardian_identifier?: string;
}): Promise<{ learner_id: string; nomination_id: string; amber_flag_count: number }> {
  const r = await fetch(`${BASE}/nomination`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`POST /nomination -> ${r.status}`);
  return r.json();
}

export async function runDemoScreening(token: string): Promise<any> {
  const r = await fetch(`${BASE}/admin/demo-screening?token=${encodeURIComponent(token)}`);
  if (!r.ok) throw new Error(`demo-screening -> ${r.status}`);
  return r.json();
}
