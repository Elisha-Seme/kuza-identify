import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  BookOpen, Gavel, UserPlus, ListChecks, RotateCw, Play, TriangleAlert,
  ShieldCheck, Check, Pause, X, Languages, Info, CircleCheck, Sparkles,
  Calculator, Puzzle, Workflow, Brain, ArrowRight, RefreshCw, Mic, MicOff,
  MessageCircle, MessageSquareText, Smartphone, FileText, Layers, ClipboardList,
  CircleDot, Clock,
} from "lucide-react";
import {
  BonusItem, ChecklistItem, FlaggedProfile, Health, Metrics, PortfolioSubmissionRow,
  ScreeningItem, SchoolRow,
  getHealth, getIntro, getMetrics, getNominationForm, listBonusItems, listFlagged,
  listItems, listSchools, recordDecision, runDemoScreening, submitNomination,
  submitPortfolio,
} from "./api";

type Tab = "about" | "review" | "refer" | "screening";
type ReferSub = "nominate" | "portfolio";
type ScreeningSub = "core" | "bonus" | "try";
type PreviewChannel = "whatsapp" | "sms" | "ussd";

const DOMAIN_LABELS: Record<string, string> = {
  numerical_reasoning: "Numeracy", verbal_reasoning: "Verbal",
  pattern_recognition: "Patterns", logical_reasoning: "Logic", working_memory: "Memory",
};
const DOMAIN_ICON: Record<string, typeof BookOpen> = {
  numerical_reasoning: Calculator, verbal_reasoning: Languages,
  pattern_recognition: Puzzle, logical_reasoning: Workflow, working_memory: Brain,
};
function DIcon({ domain, size = 18, chip = false }: { domain: string; size?: number; chip?: boolean }) {
  const I = DOMAIN_ICON[domain] || Brain;
  if (!chip) return <I size={size} className="lic" />;
  return <span className="iconchip"><I size={size} className="lic" /></span>;
}

/** Small coloured pill for a decision status, reused everywhere a status is
 * shown (queue cards, profile header, decision history) so the same status
 * always carries the same icon. */
const STATUS_ICON: Record<string, typeof Check> = {
  awaiting: Clock, advanced: Check, advance: Check, held: Pause, hold: Pause,
  declined: X, decline: X,
};
function StatusBadge({ status, label }: { status: string; label: string }) {
  const I = STATUS_ICON[status] || Clock;
  return <span className={"badge " + status}><I size={11} className="lic" />{label}</span>;
}
const SOURCE_LABELS: Record<string, string> = {
  active_screening: "Screening response",
  nomination: "Teacher or parent nomination",
  passive_signal: "School-records signal",
};
const STATUS_LABELS: Record<string, string> = {
  awaiting: "Awaiting review", advanced: "Advanced", held: "Held", declined: "Declined",
};
const DECISION_HELP: Record<string, string> = {
  advance: "Advance moves the learner forward for support (mentor matching). It is written to the audit log.",
  hold: "Hold keeps the learner in the queue for more evidence or a second reviewer. A reason is required.",
  decline: "Decline records that the learner is not advanced from this screening. A reason is required. It can be changed only by a later review.",
};
function statusOf(p: FlaggedProfile): "awaiting" | "advanced" | "held" | "declined" {
  return (p.existing_decision as any) || "awaiting";
}

/** Real, working voice input using the browser's own speech recognition
 * (Web Speech API), free, no server credential, works today in this preview.
 * This is intentionally distinct from real WhatsApp voice notes, which need
 * Twilio (for the audio) plus a separate speech-to-text provider (Claude does
 * not transcribe audio), see services/transcription/service.py. Feature-
 * detected: hides itself if the browser has no SpeechRecognition support. */
function VoiceMicButton({ lang, onResult }: { lang: "en" | "sw"; onResult: (text: string) => void }) {
  const [listening, setListening] = useState(false);
  const recRef = useRef<any>(null);
  useEffect(() => {
    const Ctor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    recRef.current = Ctor ? new Ctor() : null;
  }, []);

  function toggle() {
    const rec = recRef.current;
    if (!rec) return;
    if (listening) { rec.stop(); return; }
    rec.lang = lang === "sw" ? "sw-KE" : "en-KE";
    rec.interimResults = false;
    rec.onresult = (e: any) => {
      const text = Array.from(e.results).map((r: any) => r[0].transcript).join(" ");
      onResult(text);
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    rec.start();
    setListening(true);
  }

  const hasSupport = typeof window !== "undefined" &&
    ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
  if (!hasSupport) return null;
  return (
    <button type="button" className={"micbtn" + (listening ? " on" : "")} onClick={toggle}>
      {listening ? <MicOff size={15} className="lic" /> : <Mic size={15} className="lic" />}
      {listening ? "Stop recording" : "Answer by voice"}
    </button>
  );
}

function Mascot({ src, size = 56, float = false }: { src: string; size?: number; float?: boolean }) {
  return (
    <img src={src} alt="" width={size} height={size}
      className={"mascotimg" + (float ? " floaty" : "")}
      onError={(e) => (e.currentTarget.style.display = "none")} />
  );
}

/** Second-level navigation used inside "Refer a learner" and "Screening", so
 * each newly-built feature area (portfolio, bonus items, per-channel preview)
 * has a visible home instead of being buried or crowding the top nav. */
function SubNav<T extends string>({
  items, value, onChange,
}: { items: { id: T; label: string; icon: ReactNode }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="subnav" role="tablist" aria-label="Section">
      {items.map((it) => (
        <button key={it.id} role="tab" aria-selected={value === it.id}
          className={value === it.id ? "on" : ""} onClick={() => onChange(it.id)}>
          {it.icon}{it.label}
        </button>
      ))}
    </div>
  );
}

export function App() {
  const [tab, setTab] = useState<Tab>("about");
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(!navigator.onLine);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
    const on = () => setOffline(false), off = () => setOffline(true);
    window.addEventListener("online", on); window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  const TABS: { id: Tab; label: string; icon: ReactNode; purpose: string }[] = [
    { id: "about", label: "How it works", icon: <BookOpen size={16} className="lic" />, purpose: "What this pilot does, what is live, and what is coming next." },
    { id: "review", label: "Panel review", icon: <Gavel size={16} className="lic" />, purpose: "Review flagged learners and record decisions." },
    { id: "refer", label: "Refer a learner", icon: <UserPlus size={16} className="lic" />, purpose: "Nominate a child, or submit a portfolio / work sample as evidence." },
    { id: "screening", label: "Screening", icon: <ListChecks size={16} className="lic" />, purpose: "The core and bonus questions, and a hands-on preview of WhatsApp, SMS, and USSD." },
  ];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <Mascot src="/mascot.png" size={52} />
          <div>
            <h1>Kuza Connect</h1>
            <p className="tagline">Gifted-learner identification for under-resourced schools. The system flags candidates. A reviewer decides every case.</p>
          </div>
        </div>
        {health && (
          <div className="provider">
            <span className="grp"><span className={"dot " + (health.llm_scoring === "live" ? "live" : "mock")} />
              Scoring: <strong>{health.llm_scoring === "live" ? "Live Claude" : "Demo scorer"}</strong></span>
            <span className="grp"><span className="dot mock" />
              WhatsApp: <strong>{health.whatsapp_provider === "mock" ? "Not connected" : health.whatsapp_provider}</strong></span>
          </div>
        )}
      </header>

      {offline && <div className="offline">You are offline. Showing what is already loaded. Reconnect to refresh.</div>}

      <nav className="tabs" aria-label="Sections">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "on" : ""} aria-current={tab === t.id} onClick={() => setTab(t.id)}>
            {t.icon}{t.label}
          </button>
        ))}
      </nav>
      <p className="tabpurpose">{TABS.find((t) => t.id === tab)?.purpose}</p>

      <main className="content" key={tab}>
        {tab === "about" && <AboutTab />}
        {tab === "review" && <ReviewTab health={health} />}
        {tab === "refer" && <ReferTab />}
        {tab === "screening" && <ScreeningTab />}
      </main>
    </div>
  );
}

/* =============================== Review ================================== */
function ReviewTab({ health }: { health: Health | null }) {
  const [profiles, setProfiles] = useState<FlaggedProfile[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewerId, setReviewerId] = useState(() => localStorage.getItem("kuza_reviewer") || "reviewer-1");
  const [selected, setSelected] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [demoMsg, setDemoMsg] = useState<string | null>(null);

  async function refresh() {
    try { setError(null); setProfiles(await listFlagged()); }
    catch (e) { setError(String(e)); setProfiles([]); }
  }
  useEffect(() => { refresh(); }, []);
  useEffect(() => { localStorage.setItem("kuza_reviewer", reviewerId); }, [reviewerId]);

  async function runDemo() {
    const token = localStorage.getItem("kuza_admin_token") ||
      window.prompt("Enter the admin token to run a live demo screening:") || "";
    if (!token) return;
    localStorage.setItem("kuza_admin_token", token);
    setDemoMsg("Running a screening through the scorer.");
    try { const r = await runDemoScreening(token); setDemoMsg("New profile created (scored by " + r.scored_by + "). Refreshed."); await refresh(); }
    catch (e) { setDemoMsg("Demo failed: " + String(e)); }
  }

  const filtered = useMemo(() => (profiles || []).filter((p) => {
    if (statusFilter !== "all" && statusOf(p) !== statusFilter) return false;
    if (sourceFilter !== "all" && p.learner_source !== sourceFilter) return false;
    if (search && !p.learner_id.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  }), [profiles, statusFilter, sourceFilter, search]);
  const current = filtered.find((p) => p.session_id === selected) || filtered[0];
  const counts = useMemo(() => {
    const c = { awaiting: 0, advanced: 0, held: 0, declined: 0 };
    for (const p of profiles || []) c[statusOf(p)]++;
    return c;
  }, [profiles]);

  return (
    <div>
      <div className="pageheader">
        <h2 className="pagetitle">Panel review</h2>
        <p className="lead">Learners the system flagged for review. Filter, open one, read the evidence, then record a decision.</p>
      </div>

      <div className="statrow">
        <div className="statcard awaiting"><span className="iconchip"><Clock size={16} className="lic" /></span>
          <div><div className="n">{counts.awaiting}</div><div className="lbl">{STATUS_LABELS.awaiting}</div></div></div>
        <div className="statcard advanced"><span className="iconchip"><Check size={16} className="lic" /></span>
          <div><div className="n">{counts.advanced}</div><div className="lbl">{STATUS_LABELS.advanced}</div></div></div>
        <div className="statcard held"><span className="iconchip"><Pause size={16} className="lic" /></span>
          <div><div className="n">{counts.held}</div><div className="lbl">{STATUS_LABELS.held}</div></div></div>
        <div className="statcard declined"><span className="iconchip"><X size={16} className="lic" /></span>
          <div><div className="n">{counts.declined}</div><div className="lbl">{STATUS_LABELS.declined}</div></div></div>
      </div>

      <div className="rowbar">
        <div className="controls">
          <span className="revfield">Reviewer <input value={reviewerId} onChange={(e) => setReviewerId(e.target.value)} /></span>
          <button onClick={refresh}><RotateCw size={15} className="lic" />Refresh</button>
          <button onClick={runDemo}><Play size={15} className="lic" />Run demo screening</button>
        </div>
      </div>

      {health && health.whatsapp_provider === "mock" && (
        <div className="banner warn"><TriangleAlert size={16} className="lic" />
          <span>Demo mode. No WhatsApp provider is connected, so this data is seed data.</span></div>
      )}
      {demoMsg && <div className="banner info"><Info size={16} className="lic" /><span>{demoMsg}</span></div>}
      {error && <div className="error">Could not reach the API. {error}</div>}

      <div className="filters">
        <label>Status
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">All</option><option value="awaiting">Awaiting review</option>
            <option value="advanced">Advanced</option><option value="held">Held</option><option value="declined">Declined</option>
          </select>
        </label>
        <label>Source
          <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
            <option value="all">All</option><option value="active_screening">Screening response</option>
            <option value="nomination">Nomination</option><option value="passive_signal">Records signal</option>
          </select>
        </label>
        <label>Find learner (anonymised id)
          <input placeholder="e.g. 7a381663" value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
      </div>

      {profiles === null ? (
        <div className="loading">Loading queue.</div>
      ) : (
        <div className="split">
          <aside>
            <h3>Queue ({filtered.length})</h3>
            {filtered.length === 0 ? (
              <div className="emptybox">
                <Mascot src="/mascot.png" size={44} />
                <p>No learners match these filters.</p>
                <div className="emptyactions">
                  <button onClick={refresh}><RotateCw size={15} className="lic" />Refresh</button>
                  <button onClick={runDemo}><Play size={15} className="lic" />Run demo screening</button>
                </div>
              </div>
            ) : (
              <ul className="queue">
                {filtered.map((p) => (
                  <li key={p.session_id} className={current?.session_id === p.session_id ? "active" : ""}
                    tabIndex={0} role="button"
                    onClick={() => setSelected(p.session_id)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(p.session_id); } }}>
                    <div className="cardtop">
                      <StatusBadge status={statusOf(p)} label={STATUS_LABELS[statusOf(p)]} />
                      <span className="source">{SOURCE_LABELS[p.learner_source] ?? p.learner_source}</span>
                    </div>
                    <div className="cardline">
                      <code>{p.learner_id.slice(0, 8)}</code>
                      <span className="muted">{p.flags.length} flag(s)</span>
                      <span className="muted">{p.received_at ? new Date(p.received_at).toLocaleDateString() : ""}</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </aside>
          <section className="panel">
            {current ? <ProfileView key={current.session_id} profile={current} reviewerId={reviewerId} onDecided={refresh} />
              : <p className="muted">No learner selected.</p>}
          </section>
        </div>
      )}
    </div>
  );
}

function plainSummary(p: FlaggedProfile): string {
  if (!p.profile.length) return "Flagged for review.";
  const top = [...p.profile].sort((a, b) => b.adjusted_score - a.adjusted_score)[0];
  const low = [...p.profile].sort((a, b) => a.adjusted_score - b.adjusted_score)[0];
  return `Strongest in ${DOMAIN_LABELS[top.domain] ?? top.domain} (${top.adjusted_score} of 100). Weakest in ${DOMAIN_LABELS[low.domain] ?? low.domain} (${low.adjusted_score} of 100). Uneven profile.`;
}

function ProfileView({ profile, reviewerId, onDecided }: { profile: FlaggedProfile; reviewerId: string; onDecided: () => void; }) {
  const [pending, setPending] = useState<null | "advance" | "hold" | "decline">(null);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function confirm() {
    if (!pending) return;
    if ((pending === "hold" || pending === "decline") && notes.trim().length === 0) {
      setMsg("A written reason is required to Hold or Decline."); return;
    }
    setBusy(true); setMsg(null);
    try { await recordDecision(profile.session_id, reviewerId, pending, notes); setPending(null); setNotes(""); onDecided(); }
    catch (e) { setMsg(String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <div className="detailhead">
        <h2>Learner <code>{profile.learner_id.slice(0, 8)}</code></h2>
        <StatusBadge status={statusOf(profile)} label={STATUS_LABELS[statusOf(profile)]} />
      </div>
      <div className="metaline">
        <span className="source">{SOURCE_LABELS[profile.learner_source] ?? profile.learner_source}</span>
        <span>Received {profile.received_at ? new Date(profile.received_at).toLocaleString() : "unknown"}</span>
        <span>Channel {profile.channel}</span>
      </div>
      <p className="summary">{plainSummary(profile)}</p>

      <section>
        <h3>Evidence quality</h3>
        <div className="quality">
          <span><Languages size={15} className="lic" /> Language: <b>{profile.language === "sw" ? "Kiswahili" : "English"}</b></span>
          <span>Answered: <b>{profile.responses_count} of {profile.expected_items}</b></span>
          <span>Scored by: <b className={profile.scored_live ? "good" : "warn"}>{profile.scored_live ? "Live Claude" : "Demo data"}</b></span>
        </div>
        <p className="muted small" style={{ marginTop: 6 }}>What could change this assessment: a fuller session, a check in the other language, or a misread question. Scores rate reasoning, not correctness, so treat a single low score with care.</p>
      </section>

      <section>
        <h3>Why it was flagged</h3>
        {profile.flags.map((f) => (
          <div className="flag" key={f.id}>
            <strong>{f.rule_id.includes("spike")
              ? "A standout spike in one skill."
              : "Very uneven across skills. This pattern can indicate twice-exceptional and needs human review, not a diagnosis."}</strong>
            <div className="muted small">{f.rule_description}</div>
          </div>
        ))}
      </section>

      <section>
        <h3>Score in each thinking skill</h3>
        <p className="muted small">Skills stay separate. There is no single combined score. The adjusted value applies the school resource-tier factor for fairness.</p>
        <div className="scores">
          {profile.profile.map((d) => (
            <div className="scorerow" key={d.domain}>
              <div className="scorehead">
                <span className="name"><DIcon domain={d.domain} size={16} chip />{DOMAIN_LABELS[d.domain] ?? d.domain}</span>
                <span className="nums">raw <b>{d.raw_score}</b> · factor {d.adjustment_factor.toFixed(2)} · <span className="adj">{d.adjusted_score}</span></span>
              </div>
              <div className="scorebar"><span style={{ width: `${Math.max(0, Math.min(100, d.adjusted_score))}%` }} /></div>
              <div className="scoreev">{d.evidence_text}</div>
            </div>
          ))}
        </div>
      </section>

      <div className="three">
        <section style={{ margin: 0 }}>
          <h3>Nomination notes</h3>
          <p className="small">Twice-exceptional signs ticked: <b>{profile.nomination_amber_flags}</b> <span className="muted">(context, not a score)</span></p>
        </section>
        <section style={{ margin: 0 }}>
          <h3>Records signal</h3>
          {profile.candidate_signals.length === 0 ? <p className="muted small">None.</p> :
            profile.candidate_signals.map((s) => <div key={s.id} className="muted small">{s.signal_type}, {s.confidence} confidence (advisory only)</div>)}
        </section>
        <section style={{ margin: 0 }}>
          <h3>Portfolio evidence</h3>
          {profile.portfolio_submissions.length === 0 ? <p className="muted small">None.</p> :
            profile.portfolio_submissions.map((p) => (
              <div key={p.id} className="portfoliorow">
                <div className="portfoliotop"><FileText size={13} className="lic" /><b>{p.title}</b></div>
                <p className="muted small">{p.description}</p>
                <p className="muted small">Submitted by {p.submitted_by_role}, {new Date(p.submitted_at).toLocaleDateString()}{p.external_reference ? ". Reference: " + p.external_reference : ""}</p>
              </div>
            ))}
        </section>
      </div>

      {profile.review_history.length > 0 && (
        <section>
          <h3>Decision history</h3>
          <ul className="history">
            {profile.review_history.map((r, i) => (
              <li key={i}><StatusBadge status={r.decision} label={r.decision} />
                <span className="muted small">{r.reviewer_id}, {new Date(r.decided_at).toLocaleString()}{r.notes ? ". " + r.notes : ""}</span></li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3>Record a decision</h3>
        <div className="decisionbar">
          <button className="advance" disabled={busy} onClick={() => { setPending("advance"); setMsg(null); }}><Check size={16} className="lic" />Advance</button>
          <button className="hold" disabled={busy} onClick={() => { setPending("hold"); setMsg(null); }}><Pause size={16} className="lic" />Hold</button>
          <button className="decline" disabled={busy} onClick={() => { setPending("decline"); setMsg(null); }}><X size={16} className="lic" />Decline</button>
        </div>
        {msg && !pending && <p className="error" style={{ marginTop: 10 }}>{msg}</p>}
      </section>

      {pending && (
        <div className="modalback" role="dialog" aria-modal="true" onClick={() => setPending(null)}>
          <div className="modal reveal" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ textTransform: "capitalize" }}>Confirm: {pending}</h2>
            <p className="small" style={{ margin: "8px 0" }}>{DECISION_HELP[pending]}</p>
            <div className="field">
              <label>Reason or notes {(pending === "hold" || pending === "decline") && <span className="ext">(required)</span>}</label>
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Why this decision?" autoFocus />
            </div>
            {msg && <p className="error">{msg}</p>}
            <div className="decisionbar">
              <button className={pending} disabled={busy} onClick={confirm}>Confirm {pending}</button>
              <button onClick={() => setPending(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* =========================== Refer a learner ============================= */
function ReferTab() {
  const [sub, setSub] = useState<ReferSub>("nominate");
  return (
    <div>
      <SubNav<ReferSub>
        value={sub} onChange={setSub}
        items={[
          { id: "nominate", label: "Nomination", icon: <UserPlus size={15} className="lic" /> },
          { id: "portfolio", label: "Portfolio / work sample", icon: <FileText size={15} className="lic" /> },
        ]}
      />
      {sub === "nominate" && <NominateTab />}
      {sub === "portfolio" && <PortfolioTab />}
    </div>
  );
}

const DRAFT_KEY = "kuza_nomination_draft";
function NominateTab() {
  const [form, setForm] = useState<ChecklistItem[]>([]);
  const [schools, setSchools] = useState<SchoolRow[]>([]);
  const [schoolId, setSchoolId] = useState("");
  const [role, setRole] = useState<"teacher" | "parent" | "peer">("teacher");
  const [answers, setAnswers] = useState<Record<string, boolean>>({});
  const [observation, setObservation] = useState("");
  const [ageRange, setAgeRange] = useState("");
  const [consent, setConsent] = useState(false);
  const [result, setResult] = useState<{ id: string; amber: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getNominationForm().then(setForm).catch((e) => setError(String(e)));
    listSchools().then((s) => { setSchools(s); if (s[0]) setSchoolId(s[0].id); }).catch(() => {});
    try { const d = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null");
      if (d) { setAnswers(d.answers || {}); setObservation(d.observation || ""); setAgeRange(d.ageRange || ""); setRole(d.role || "teacher"); }
    } catch { /* ignore */ }
  }, []);

  function saveDraft() {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({ answers, observation, ageRange, role }));
    setError(null); setResult(null); alert("Draft saved on this device. You can continue later.");
  }

  async function submit() {
    setResult(null); setError(null);
    if (!consent) { setError("Please confirm consent to nominate before submitting."); return; }
    try {
      const r = await submitNomination({
        school_id: schoolId, nominator_role: role,
        checklist_responses: { ...answers, _observation: observation || undefined, _age_range: ageRange || undefined },
        guardian_identifier: `web-${role}-consent`,
      });
      setResult({ id: r.nomination_id, amber: r.amber_flag_count });
      setAnswers({}); setObservation(""); setAgeRange(""); setConsent(false); localStorage.removeItem(DRAFT_KEY);
    } catch (e) { setError(String(e)); }
  }

  return (
    <div>
      <div className="pageheader">
        <h2 className="pagetitle">Nominate a child</h2>
        <p className="lead">A teacher or parent refers a learner who seems capable. Marked items are twice-exceptional signs (gifted, but also struggling in a way that hides it). This is a referral for screening, not a diagnosis.</p>
      </div>
      <div className="formcard">
      <div className="safeguard"><ShieldCheck size={18} className="lic" />
        <span>Do not enter the learner’s name or any medical information. Refer only learners you teach or are guardian to. A referral invites the learner to a short screening. A human panel reviews everything before any decision.</span></div>

      <div className="field"><label>School
        <select value={schoolId} onChange={(e) => setSchoolId(e.target.value)}>
          {schools.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.tier})</option>)}
        </select></label></div>
      <div className="field"><label>I am a
        <select value={role} onChange={(e) => setRole(e.target.value as any)}>
          <option value="teacher">Teacher</option><option value="parent">Parent or guardian</option>
          <option value="peer">Peer or classmate</option>
        </select></label></div>
      {role === "peer" && (
        <div className="banner info small">A peer nomination is shown to the panel as lower-confidence context, alongside any teacher or parent evidence. It cannot advance a learner on its own, and it works best when a teacher can confirm it.</div>
      )}
      <div className="field"><label>Approximate class or age range (optional)
        <input value={ageRange} onChange={(e) => setAgeRange(e.target.value)} placeholder="e.g. Grade 4, or about 9 to 10 years" /></label></div>

      <div className="checklist">
        {form.map((c) => (
          <label key={c.key} className={"check " + (c.amber_flag ? "amber" : "")}>
            <input type="checkbox" checked={!!answers[c.key]} onChange={(e) => setAnswers({ ...answers, [c.key]: e.target.checked })} />
            <span>{c.amber_flag && <TriangleAlert size={14} className="lic" style={{ color: "var(--amber)" }} />} {c.prompt_en}</span>
          </label>
        ))}
      </div>

      <div className="field"><label>Anything you have observed (optional, no names)
        <textarea value={observation} onChange={(e) => setObservation(e.target.value)} placeholder="e.g. explains ideas well aloud but freezes on written tests" /></label></div>

      <label className="consent">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>I confirm I have the appropriate consent to nominate this child for screening.</span>
      </label>

      <div className="decisionbar" style={{ marginTop: 16 }}>
        <button className="advance" disabled={!schoolId || !consent} onClick={submit}><Check size={16} className="lic" />Submit nomination</button>
        <button onClick={saveDraft}>Save draft</button>
      </div>

      {result && (
        <div className="banner ok"><CircleCheck size={18} className="lic" />
          <span>Nomination saved. Twice-exceptional signs ticked: <b>{result.amber}</b>. Tracking id <code>{result.id.slice(0, 8)}</code>. The learner now awaits screening before the panel records a decision.</span></div>
      )}
      {error && <div className="error">{error}</div>}
      </div>
    </div>
  );
}

/* =============================== Portfolio ================================ */
function PortfolioTab() {
  const [schools, setSchools] = useState<SchoolRow[]>([]);
  const [schoolId, setSchoolId] = useState("");
  const [role, setRole] = useState<"teacher" | "parent" | "peer">("teacher");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [reference, setReference] = useState("");
  const [consent, setConsent] = useState(false);
  const [result, setResult] = useState<{ learnerId: string; submissionId: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listSchools().then((s) => { setSchools(s); if (s[0]) setSchoolId(s[0].id); }).catch(() => {});
  }, []);

  async function submit() {
    setResult(null); setError(null);
    if (!consent) { setError("Please confirm consent before submitting."); return; }
    if (!title.trim() || !description.trim()) { setError("A title and a description are required."); return; }
    setBusy(true);
    try {
      const r = await submitPortfolio({
        school_id: schoolId, submitted_by_role: role, title: title.trim(),
        description: description.trim(), external_reference: reference.trim() || undefined,
      });
      setResult({ learnerId: r.learner_id, submissionId: r.submission_id });
      setTitle(""); setDescription(""); setReference(""); setConsent(false);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <div className="pageheader">
        <h2 className="pagetitle">Submit a portfolio or work sample</h2>
        <p className="lead">A fourth way a capable child is found: a description of a drawing, story, project, or piece of written work, submitted as supporting evidence. This is evidence for the panel to weigh, not a score, and not a decision.</p>
      </div>
      <div className="formcard">
      <div className="safeguard"><ShieldCheck size={18} className="lic" />
        <span>Do not enter the learner's name or any medical information. Describe the work itself, for example what the child made, said, or solved, and why it stood out to you.</span></div>

      <div className="field"><label>School
        <select value={schoolId} onChange={(e) => setSchoolId(e.target.value)}>
          {schools.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.tier})</option>)}
        </select></label></div>
      <div className="field"><label>I am a
        <select value={role} onChange={(e) => setRole(e.target.value as any)}>
          <option value="teacher">Teacher</option><option value="parent">Parent or guardian</option>
          <option value="peer">Peer or classmate</option>
        </select></label></div>
      <div className="field"><label>Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. A hand-drawn map of the school compound" /></label></div>
      <div className="field"><label>Description
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What did the child make or do, and what about the thinking behind it stood out?" /></label></div>
      <div className="field"><label>Reference (optional)
        <input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="A filing note or location for the physical item, not the item itself" /></label></div>

      <label className="consent">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>I confirm I have the appropriate consent to submit this as evidence for this child.</span>
      </label>

      <div className="decisionbar" style={{ marginTop: 16 }}>
        <button className="advance" disabled={!schoolId || busy} onClick={submit}><Check size={16} className="lic" />Submit portfolio evidence</button>
      </div>

      {result && (
        <div className="banner ok"><CircleCheck size={18} className="lic" />
          <span>Portfolio evidence saved. Tracking id <code>{result.submissionId.slice(0, 8)}</code>. It appears alongside any screening or nomination evidence for the panel to review.</span></div>
      )}
      {error && <div className="error">{error}</div>}
      </div>
    </div>
  );
}

/* ============================== Screening ================================ */
function ScreeningTab() {
  const [sub, setSub] = useState<ScreeningSub>("core");
  return (
    <div>
      <SubNav<ScreeningSub>
        value={sub} onChange={setSub}
        items={[
          { id: "core", label: "Core questions", icon: <ListChecks size={15} className="lic" /> },
          { id: "bonus", label: "Bonus questions", icon: <Layers size={15} className="lic" /> },
          { id: "try", label: "Try it interactively", icon: <Sparkles size={15} className="lic" /> },
        ]}
      />
      {sub === "core" && <QuestionsTab />}
      {sub === "bonus" && <BonusQuestionsTab />}
      {sub === "try" && <TryItTab />}
    </div>
  );
}

function QuestionsTab() {
  const [items, setItems] = useState<ScreeningItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { listItems().then(setItems).catch((e) => { setError(String(e)); setItems([]); }); }, []);
  return (
    <div>
      <div className="pageheader">
        <h2 className="pagetitle">The core screening questions</h2>
        <p className="lead">A learner answers these five questions, over WhatsApp, SMS, or USSD, in English or Kiswahili. There are no trick answers. The scorer rewards reasoning, not neat handwriting or perfect arithmetic. This is the automatic session every screening runs today.</p>
      </div>
      <div className="formcard">
      {error && <div className="error">{error}</div>}
      {items === null ? <div className="loading">Loading questions.</div> : (
        <ol className="questions">
          {items.map((it) => (
            <li key={it.id} className="qitem">
              <span className="qdomain"><DIcon domain={it.domain} size={16} chip />{DOMAIN_LABELS[it.domain] ?? it.domain}</span>
              <p className="qen">{it.prompt.en}</p>
              <p className="qsw"><Languages size={15} className="lic" /><span>Kiswahili: {it.prompt.sw}</span></p>
            </li>
          ))}
        </ol>
      )}
      </div>
    </div>
  );
}

/* ============================ Bonus questions ============================= */
function BonusQuestionsTab() {
  const [items, setItems] = useState<BonusItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { listBonusItems().then(setItems).catch((e) => { setError(String(e)); setItems([]); }); }, []);
  const TIER_LABELS: Record<string, string> = { bonus_off_level: "Off-level (harder)", bonus_creativity: "Creativity" };
  return (
    <div>
      <div className="pageheader">
        <h2 className="pagetitle">Bonus questions</h2>
        <p className="lead">Off-level (deliberately harder) items and a creativity item, built as additional evidence for a learner who finishes the core five with room to spare. They exist and are scoreable today, but are not yet wired into the automatic session, a reviewer or a future version of the gateway would need to decide when to offer them.</p>
      </div>
      <div className="formcard">
      {error && <div className="error">{error}</div>}
      {items === null ? <div className="loading">Loading bonus questions.</div> : items.length === 0 ? (
        <p className="muted small">No bonus questions available.</p>
      ) : (
        <ol className="questions">
          {items.map((it) => (
            <li key={it.id} className="qitem">
              <div className="cardtop">
                <span className="qdomain"><DIcon domain={it.domain} size={16} chip />{DOMAIN_LABELS[it.domain] ?? it.domain}</span>
                <span className="badge awaiting">{TIER_LABELS[it.tier] ?? it.tier}</span>
              </div>
              <p className="qen">{it.prompt.en}</p>
              <p className="qsw"><Languages size={15} className="lic" /><span>Kiswahili: {it.prompt.sw}</span></p>
            </li>
          ))}
        </ol>
      )}
      </div>
    </div>
  );
}

/* ============================== Try it ==================================== */
const CHANNEL_LABELS: Record<PreviewChannel, string> = { whatsapp: "WhatsApp", sms: "SMS", ussd: "USSD" };
const CHANNEL_ICON: Record<PreviewChannel, typeof MessageCircle> = { whatsapp: MessageCircle, sms: MessageSquareText, ussd: Smartphone };
const CHANNEL_NOTE: Record<PreviewChannel, string> = {
  whatsapp: "Needs a smartphone and either data or wifi. Real delivery needs Twilio (not yet connected).",
  sms: "Works on any phone with airtime and signal, no internet or app needed. Real delivery needs a connected SMS provider (not yet connected). Long answers may send as several linked text messages.",
  ussd: "Works on any phone with signal, no airtime needed at all, the learner dials a shortcode. Synchronous: one screen per reply, and a session times out after inactivity (about 180 seconds on a typical provider), shown here as information only, not a countdown, since the system's untimed accommodation still applies.",
};

function TryItTab() {
  const [intro, setIntro] = useState<{ en: string; sw: string } | null>(null);
  const [items, setItems] = useState<ScreeningItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lang, setLang] = useState<"en" | "sw">("en");
  const [channel, setChannel] = useState<PreviewChannel>("whatsapp");
  const [step, setStep] = useState(0); // 0 = intro, 1..N = items, N+1 = done
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState("");

  useEffect(() => {
    Promise.all([getIntro(), listItems()])
      .then(([i, its]) => { setIntro(i); setItems(its); })
      .catch((e) => setError(String(e)));
  }, []);

  function restart() {
    setStep(0); setAnswers({}); setDraft("");
  }

  function next(answer: string) {
    const current = items?.[step - 1];
    if (current) setAnswers((a) => ({ ...a, [current.id]: answer }));
    setDraft("");
    setStep((s) => s + 1);
  }

  if (error) return <div className="formcard"><div className="error">{error}</div></div>;
  if (!intro || !items) return <div className="formcard"><div className="loading">Loading preview.</div></div>;

  const total = items.length;
  const done = step > total;
  const current = !done && step > 0 ? items[step - 1] : null;
  const isUssd = channel === "ussd";
  const frame = (text: string) => (isUssd ? (done ? "END " : "CON ") + text : text);

  return (
    <div>
      <div className="pageheader tryhead">
        <div className="tryheadleft">
          <Mascot src="/mascot.png" size={44} />
          <div>
            <h2 className="pagetitle" style={{ fontSize: 22 }}>Try the screener</h2>
            <p className="muted small">A preview of the real questions, at your own pace. Switch channel below to see how WhatsApp, SMS, and USSD actually differ. Nothing you type or say here is saved, scored, or sent anywhere.</p>
          </div>
        </div>
        <div className="langtoggle" role="group" aria-label="Preview language">
          <button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>EN</button>
          <button className={lang === "sw" ? "on" : ""} onClick={() => setLang("sw")}>SW</button>
        </div>
      </div>
      <div className="formcard tryit">

      <div className="channeltoggle" role="group" aria-label="Preview channel">
        {(["whatsapp", "sms", "ussd"] as PreviewChannel[]).map((c) => {
          const I = CHANNEL_ICON[c];
          return (
            <button key={c} className={channel === c ? "on" : ""} onClick={() => setChannel(c)}>
              <I size={15} className="lic" />{CHANNEL_LABELS[c]}
            </button>
          );
        })}
      </div>
      <p className="muted small channelnote"><Info size={13} className="lic" />{CHANNEL_NOTE[channel]}</p>

      <div className="dots" aria-hidden>
        {Array.from({ length: total }).map((_, i) => {
          const cls = done || i < step - 1 ? "on" : i === step - 1 ? "cur" : "";
          return <span key={i} className={"dot2 " + cls} />;
        })}
      </div>

      <div className={"chatarea " + channel}>
        {step === 0 && (
          <div className={"bubble reveal" + (isUssd ? " ussdscreen" : "")}>
            <p>{frame(intro[lang])}</p>
            <button className="advance" onClick={() => setStep(1)}>Start <ArrowRight size={16} className="lic" /></button>
          </div>
        )}

        {current && (
          <div className={"bubble reveal" + (isUssd ? " ussdscreen" : "")} key={current.id}>
            <span className="qdomain"><DIcon domain={current.domain} size={16} />{DOMAIN_LABELS[current.domain] ?? current.domain}</span>
            <p className="qtext">{frame(current.prompt[lang])}</p>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={lang === "sw" ? "Andika jibu lako hapa..." : "Type your answer here..."}
            />
            {channel === "sms" && (
              <p className={"charcount" + (draft.length > 160 ? " warn" : "")}>{draft.length}/160 characters (a typical single SMS; longer answers send as linked messages)</p>
            )}
            {channel === "whatsapp" && (
              <div className="miccontrol">
                <VoiceMicButton lang={lang} onResult={(t) => setDraft((d) => (d ? d + " " + t : t))} />
              </div>
            )}
            <div className="decisionbar">
              <button className="advance" onClick={() => next(draft)}>
                {step === total ? "Finish" : "Next"} <ArrowRight size={16} className="lic" />
              </button>
              <button onClick={() => next("")}>Skip this one</button>
            </div>
          </div>
        )}

        {done && (
          <div className={"bubble reveal donecard" + (isUssd ? " ussdscreen" : "")}>
            <Mascot src="/mascot-thumb.png" size={72} float />
            <h3 className="doneheading">{frame("Thank you")}</h3>
            <p>In a real session, a person on the review panel would read the reasoning behind these answers, not just check them right or wrong. There is still no time limit, no score shown to the learner, and no decision made by AI.</p>
            <button onClick={restart}><RefreshCw size={16} className="lic" />Try it again</button>
          </div>
        )}
      </div>
      </div>
    </div>
  );
}

/* ========================= Feature status (About) ========================= */
type FeatureStatus = "live" | "soon";
const FEATURES: { label: string; status: FeatureStatus; note: string; icon: typeof BookOpen }[] = [
  { label: "Screening: WhatsApp, SMS, USSD", status: "live", icon: MessageCircle,
    note: "Session logic and Claude scoring are live; all three run on mock providers until a real one is connected." },
  { label: "Nomination", status: "live", icon: UserPlus,
    note: "Teacher, parent, or peer referral with a twice-exceptional checklist." },
  { label: "Portfolio / work sample", status: "live", icon: FileText,
    note: "Description-based evidence, reviewed alongside screening and nomination." },
  { label: "Bonus questions", status: "live", icon: Layers,
    note: "Off-level and creativity items exist as preview content, not yet in the automatic session." },
  { label: "Human panel review and audit log", status: "live", icon: Gavel,
    note: "A person decides Advance, Hold, or Decline. Every flag-to-decision path is logged." },
  { label: "Voice-note answers (this web preview)", status: "live", icon: Mic,
    note: "Free, browser-based speech-to-text. A real WhatsApp voice note still needs a transcription provider." },
  { label: "Real WhatsApp and SMS delivery", status: "soon", icon: MessageSquareText,
    note: "Needs a Twilio account, sender numbers, and approved message templates." },
  { label: "Real USSD delivery", status: "soon", icon: Smartphone,
    note: "Needs an Africa's Talking account and a shortcode." },
  { label: "Voice-note transcription (WhatsApp)", status: "soon", icon: ClipboardList,
    note: "Needs a dedicated speech-to-text provider and its own API key. Claude does not transcribe audio." },
  { label: "School-records / KEMIS integration", status: "soon", icon: BookOpen,
    note: "Discovery only so far. No confirmed, authorised data route exists yet." },
];

function FeatureStatusGrid() {
  return (
    <div>
      <h3>What is live now, and what is coming</h3>
      <div className="statusgrid">
        {FEATURES.map((f) => {
          const Icon = f.icon;
          return (
            <div className="statuscard" key={f.label}>
              <div className="statustop">
                <span className={"iconchip sm" + (f.status === "soon" ? " amber" : "")}><Icon size={14} className="lic" /></span>
                <span className={"tag " + f.status}>
                  {f.status === "live"
                    ? <><CircleDot size={10} className="lic" />Live</>
                    : <><Clock size={10} className="lic" />Coming</>}
                </span>
              </div>
              <b>{f.label}</b>
              <p className="muted small">{f.note}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* =============================== About ================================== */
function AboutTab() {
  const [m, setM] = useState<Metrics | null>(null);
  useEffect(() => { getMetrics().then(setM).catch(() => setM(null)); }, []);

  return (
    <div>
      <div className="pageheader aboutheader">
        <h2 className="pagetitle">How Kuza Connect works</h2>
        <div className="abouthero"><Mascot src="/mascot-wave.png" size={84} float /><Mascot src="/mascot.png" size={84} /></div>
      </div>
      <div className="formcard prose">
      <FeatureStatusGrid />

      <div className="aboutflow">
        <div className="abt">
          <h3>The problem</h3>
          <p>In under-resourced Kenyan schools, capable learners are routinely missed. This is most true for twice-exceptional children, who are gifted and also face a challenge such as ADHD or dyslexia, so they read as average. Timed, single-score tests hide the learners we most want to find.</p>
        </div>
        <div className="abt">
          <h3>What exists today (Phase 0 pilot)</h3>
          <p>A narrow, human-supervised slice: structured screening over WhatsApp, SMS, or USSD, teacher, parent, or peer nomination, portfolio evidence, context-adjusted spike-based scoring, and a review panel where a person decides on every flag. There is no automated diagnosis or placement. It currently runs on demo data, and every channel is in demo mode until a real provider (Twilio for WhatsApp and SMS, Africa's Talking for USSD) is connected.</p>
        </div>
        <div className="abt">
          <h3>Four ways a child is found</h3>
          <ul>
            <li><b>Screening response.</b> The child answers reasoning questions, over WhatsApp, SMS, or USSD, no smartphone or internet required for the last two.</li>
            <li><b>Teacher, parent, or peer nomination.</b> A structured referral form; a peer referral is shown as lower-confidence context, never equal-weight with an adult's.</li>
            <li><b>Portfolio or work sample.</b> A description of a drawing, writing, or project, as supporting evidence.</li>
            <li><b>School-records signal.</b> A background job spots uneven grade patterns (spreadsheet only, no OCR yet).</li>
          </ul>
        </div>
        <div className="abt">
          <h3>The five core reasoning domains</h3>
          <ul className="domainlist">
            {Object.entries(DOMAIN_LABELS).map(([k, v]) => (
              <li key={k}><DIcon domain={k} size={17} chip />{v}</li>
            ))}
          </ul>
          <p className="muted small" style={{ marginTop: 8 }}>Off-level (harder) items and a creativity item exist as additional evidence content but are not yet part of the automatic session, see Screening &gt; Bonus questions.</p>
        </div>
        <div className="abt">
          <h3>How Claude scoring works</h3>
          <p>Claude reads each open-ended answer and rates the reasoning from 0 to 100, with a short written evidence note, in English or Kiswahili. It scores reasoning and gives evidence. It does not diagnose, label, or decide.</p>
        </div>
        <div className="abt">
          <h3>Context adjustment, and no composite score</h3>
          <p>Scores are adjusted against the school resource tier, so a learner is not judged against a richer school baseline. Domains are never collapsed into one number. The system flags on the highest single-domain score and on unevenness, which is what surfaces twice-exceptional profiles.</p>
        </div>
        <div className="abt">
          <h3>Human review, audit, privacy</h3>
          <p>The AI flags and explains. A person records Advance, Hold, or Decline (Hold and Decline require a reason). Every flag-to-decision path is written to an append-only audit log. The data model stores no name, no diagnosis, and no health field. Consent is captured before screening.</p>
        </div>
        <div className="abt">
          <h3>What this system does not do</h3>
          <ul className="donts">
            <li>It does not diagnose ADHD, dyslexia, giftedness, or any medical condition.</li>
            <li>It does not auto-advance, auto-place, or auto-enrol any child.</li>
            <li>It does not compute a single combined score.</li>
            <li>It does not store names or health data, or decide without a human.</li>
          </ul>
        </div>
        <div className="abt span">
          <h3>Live capabilities and current limits</h3>
          <div className="two">
            <div><b>Live now</b>
              <ul><li>Screening, Claude scoring, flags</li><li>Teacher, parent, and peer nomination (2e checklist)</li><li>Portfolio / work-sample evidence</li><li>WhatsApp, SMS, and USSD session logic (all mock providers)</li><li>Off-level and creativity bonus items (preview only)</li><li>Human review and audit log</li><li>Context adjustment (tier lookup)</li><li>Records signal from spreadsheets</li></ul></div>
            <div><b>Not yet</b>
              <ul><li>Real WhatsApp/SMS (Twilio) or USSD (Africa's Talking)</li><li>Voice-note transcription (needs a speech-to-text provider, interface only)</li><li>Trained context model</li><li>OCR of paper records</li><li>KEMIS or KNEC integration</li><li>Reviewer accounts</li></ul></div>
          </div>
        </div>
      </div>

      {m && (
        <>
          <h3>Pilot counts (demo data)</h3>
          <table className="counts">
            <tbody>
              {["screened", "flagged", "reviewed", "advanced", "held", "declined", "awaiting_review"].map((k) => (
                <tr key={k}><th>{k.replace(/_/g, " ")}</th><td className="n">{m.funnel[k] ?? 0}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="muted small" style={{ marginTop: 6 }}>Deeper fairness measures (reviewer agreement, false positives and negatives) need labelled ground truth. They are a Phase 2 item and are not shown here to avoid implying data we do not have.</p>
        </>
      )}

      <h3>What we can add next</h3>
      <p className="muted small">Each item lists value, dependencies, risks, and rough effort (S, M, L). Items marked <span className="ext">external</span> need a new provider or an institutional agreement.</p>
      <div className="roadmap">
        {ROADMAP.map((r) => (
          <div className="rmitem" key={r.title}>
            <h4><span>{r.title} {r.external && <span className="ext">external</span>}</span><span className="effort">{r.effort}</span></h4>
            <dl>
              <dt>Value</dt><dd>{r.value}</dd>
              <dt>Needs</dt><dd>{r.needs}</dd>
              <dt>Risks</dt><dd>{r.risks}</dd>
            </dl>
          </div>
        ))}
      </div>
      <p className="muted small">Buildable on the current stack: reviewer assignment and status, fairness dashboards, exports, longitudinal tables, model-feedback capture. Needs a new provider or agreement: real WhatsApp/SMS (Twilio), real USSD (Africa's Talking), voice transcription, KEMIS integration, notification channels.</p>
      <p className="muted small">This dashboard is the back-office tool for trained reviewers. The child-facing part is WhatsApp, SMS, or USSD. Phase 0 pilot build.</p>
      </div>
    </div>
  );
}

const ROADMAP = [
  { title: "Real WhatsApp and SMS (Twilio)", external: true, effort: "M",
    value: "Reach real children in the field, including on a basic phone with no data plan.",
    needs: "Twilio account and sender numbers, approved WhatsApp message templates, webhook handling, consent and opt-out, retries, audit logs. The provider adapters for both channels are already built and stubbed.",
    risks: "Delivery and consent handling, message cost, personal data in transit." },
  { title: "Real USSD (Africa's Talking)", external: true, effort: "M",
    value: "Reach children with no smartphone and no internet at all, dial a shortcode, no airtime needed.",
    needs: "An Africa's Talking account and a shortcode, session-timeout handling, character-limit-aware prompts. The provider and gateway logic are already built and stubbed; USSD suits the forced-choice item far better than an open-ended one.",
    risks: "Session time-outs cut a slow thinker off mid-answer, which cuts against the untimed accommodation; best for shorter, forced-choice items." },
  { title: "Voice-note transcription", external: true, effort: "S",
    value: "A dyslexia / writing-anxiety accommodation, answer by speaking instead of typing.",
    needs: "A speech-to-text provider (OpenAI Whisper or similar) and its own API key, wired into the existing TranscriptionProvider interface. Claude does not transcribe audio. The web preview already does this for free using the browser's own speech recognition.",
    risks: "A new provider dependency and its cost; accuracy in Kiswahili and background noise need evaluation." },
  { title: "KEMIS data (discovery)", external: true, effort: "L",
    value: "Find never-nominated children from existing records.",
    needs: "First confirm the system and that an authorised route exists (data model, auth, consent basis, rate limits, MOU). No endpoint is assumed. Interim option: CSV or SFTP or manual import with audit logs, via the existing adapter interface.",
    risks: "No public write API today, legal and consent basis, re-encoding teacher bias." },
  { title: "School and teacher accounts, roles", external: false, effort: "L",
    value: "Real logins and scoped access.",
    needs: "Authentication, users and roles tables, session management.",
    risks: "Access control and credential security." },
  { title: "Reviewer assignment and In-review status", external: false, effort: "M",
    value: "Coordinate several reviewers.",
    needs: "New status and assignment columns, a migration beyond the current schema.",
    risks: "Schema change against the locked model." },
  { title: "Fairness and calibration dashboards", external: false, effort: "M",
    value: "Support the equity claim with evidence.",
    needs: "Labelled ground truth, reviewer-agreement capture, more metrics.",
    risks: "Misleading statistics on small samples." },
  { title: "Longitudinal support tracking", external: false, effort: "L",
    value: "Follow outcomes over time.",
    needs: "Outcome and follow-up tables, a link to Layer 2.",
    risks: "Long-term data governance." },
  { title: "Model recalibration from reviewer feedback", external: false, effort: "M",
    value: "Improve scoring from reviewer decisions.",
    needs: "Feedback capture, prompt and version management, an eval set.",
    risks: "Feedback loops that encode bias." },
  { title: "Exports and reporting", external: false, effort: "S",
    value: "Share de-identified statistics with partners.",
    needs: "Export endpoints, aggregation, redaction.",
    risks: "Re-identification of small groups." },
  { title: "Notifications and escalation", external: true, effort: "S",
    value: "Prompt timely reviewer action.",
    needs: "Email or SMS integration, rules.",
    risks: "Alert fatigue, personal data in notifications." },
];
