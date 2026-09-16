import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  BookOpen, Gavel, UserPlus, ListChecks, RotateCw, Play, TriangleAlert,
  ShieldCheck, Check, Pause, X, Languages, Info, CircleCheck,
} from "lucide-react";
import {
  ChecklistItem, FlaggedProfile, Health, Metrics, ScreeningItem, SchoolRow,
  getHealth, getMetrics, getNominationForm, listFlagged, listItems, listSchools,
  recordDecision, runDemoScreening, submitNomination,
} from "./api";

type Tab = "about" | "review" | "nominate" | "questions";

const DOMAIN_LABELS: Record<string, string> = {
  numerical_reasoning: "Numeracy", verbal_reasoning: "Verbal",
  pattern_recognition: "Patterns", logical_reasoning: "Logic", working_memory: "Memory",
};
const DOMAIN_SYM: Record<string, string> = {
  numerical_reasoning: "calculate", verbal_reasoning: "translate",
  pattern_recognition: "extension", logical_reasoning: "account_tree", working_memory: "memory",
};
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

function Sym({ name, size = 20 }: { name: string; size?: number }) {
  return <span className="msym" style={{ fontSize: size }} aria-hidden>{name}</span>;
}
function Mascot({ src, size = 56, float = false }: { src: string; size?: number; float?: boolean }) {
  return (
    <img src={src} alt="" width={size} height={size}
      className={"mascotimg" + (float ? " floaty" : "")}
      onError={(e) => (e.currentTarget.style.display = "none")} />
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
    { id: "about", label: "How it works", icon: <BookOpen size={16} className="lic" />, purpose: "What this pilot does and how it works." },
    { id: "review", label: "Panel review", icon: <Gavel size={16} className="lic" />, purpose: "Review flagged learners and record decisions." },
    { id: "nominate", label: "Nominate", icon: <UserPlus size={16} className="lic" />, purpose: "Refer a learner for screening." },
    { id: "questions", label: "Questions", icon: <ListChecks size={16} className="lic" />, purpose: "The five questions a learner answers." },
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
        {tab === "nominate" && <NominateTab />}
        {tab === "questions" && <QuestionsTab />}
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

  return (
    <div>
      <div className="rowbar">
        <p className="lead">Learners the system flagged for review. Filter, open one, read the evidence, then record a decision.</p>
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
              <div className="emptybox"><Mascot src="/mascot.png" size={44} /><p>No learners match these filters.</p></div>
            ) : (
              <ul className="queue">
                {filtered.map((p) => (
                  <li key={p.session_id} className={current?.session_id === p.session_id ? "active" : ""}
                    tabIndex={0} role="button"
                    onClick={() => setSelected(p.session_id)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(p.session_id); } }}>
                    <div className="cardtop">
                      <span className={"badge " + statusOf(p)}>{STATUS_LABELS[statusOf(p)]}</span>
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
        <span className={"badge " + statusOf(profile)}>{STATUS_LABELS[statusOf(profile)]}</span>
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
          <span>Scored by: <b className={profile.scored_live ? "good" : "warn"}>{profile.scored_live ? "Live Claude" : "Demo scorer"}</b></span>
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
                <span className="name"><Sym name={DOMAIN_SYM[d.domain] || "psychology"} size={18} />{DOMAIN_LABELS[d.domain] ?? d.domain}</span>
                <span className="nums">raw <b>{d.raw_score}</b> · factor {d.adjustment_factor.toFixed(2)} · <span className="adj">{d.adjusted_score}</span></span>
              </div>
              <div className="scoreev">{d.evidence_text}</div>
            </div>
          ))}
        </div>
      </section>

      <div className="two">
        <section style={{ margin: 0 }}>
          <h3>Nomination notes</h3>
          <p className="small">Twice-exceptional signs ticked: <b>{profile.nomination_amber_flags}</b> <span className="muted">(context, not a score)</span></p>
        </section>
        <section style={{ margin: 0 }}>
          <h3>Records signal</h3>
          {profile.candidate_signals.length === 0 ? <p className="muted small">None.</p> :
            profile.candidate_signals.map((s) => <div key={s.id} className="muted small">{s.signal_type}, {s.confidence} confidence (advisory only)</div>)}
        </section>
      </div>

      {profile.review_history.length > 0 && (
        <section>
          <h3>Decision history</h3>
          <ul className="history">
            {profile.review_history.map((r, i) => (
              <li key={i}><span className={"badge " + r.decision}>{r.decision}</span>
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

/* ============================== Nominate ================================= */
const DRAFT_KEY = "kuza_nomination_draft";
function NominateTab() {
  const [form, setForm] = useState<ChecklistItem[]>([]);
  const [schools, setSchools] = useState<SchoolRow[]>([]);
  const [schoolId, setSchoolId] = useState("");
  const [role, setRole] = useState<"teacher" | "parent">("teacher");
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
        guardian_identifier: role === "parent" ? "web-parent-consent" : "web-teacher-consent",
      });
      setResult({ id: r.nomination_id, amber: r.amber_flag_count });
      setAnswers({}); setObservation(""); setAgeRange(""); setConsent(false); localStorage.removeItem(DRAFT_KEY);
    } catch (e) { setError(String(e)); }
  }

  return (
    <div className="formcard">
      <h2>Nominate a child</h2>
      <p className="lead">A teacher or parent refers a learner who seems capable. Marked items are twice-exceptional signs (gifted, but also struggling in a way that hides it). This is a referral for screening, not a diagnosis.</p>

      <div className="safeguard"><ShieldCheck size={18} className="lic" />
        <span>Do not enter the learner’s name or any medical information. Refer only learners you teach or are guardian to. A referral invites the learner to a short screening. A human panel reviews everything before any decision.</span></div>

      <div className="field"><label>School
        <select value={schoolId} onChange={(e) => setSchoolId(e.target.value)}>
          {schools.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.tier})</option>)}
        </select></label></div>
      <div className="field"><label>I am a
        <select value={role} onChange={(e) => setRole(e.target.value as any)}>
          <option value="teacher">Teacher</option><option value="parent">Parent or guardian</option>
        </select></label></div>
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
  );
}

/* ========================= Screening questions ========================== */
function QuestionsTab() {
  const [items, setItems] = useState<ScreeningItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { listItems().then(setItems).catch((e) => { setError(String(e)); setItems([]); }); }, []);
  return (
    <div className="formcard">
      <h2>The screening questions</h2>
      <p className="lead">A learner answers these five questions, over WhatsApp, in English or Kiswahili. There are no trick answers. The scorer rewards reasoning, not neat handwriting or perfect arithmetic.</p>
      {error && <div className="error">{error}</div>}
      {items === null ? <div className="loading">Loading questions.</div> : (
        <ol className="questions">
          {items.map((it) => (
            <li key={it.id} className="qitem">
              <span className="qdomain"><Sym name={DOMAIN_SYM[it.domain] || "psychology"} size={18} />{DOMAIN_LABELS[it.domain] ?? it.domain}</span>
              <p className="qen">{it.prompt.en}</p>
              <p className="qsw"><Languages size={15} className="lic" /><span>Kiswahili: {it.prompt.sw}</span></p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

/* =============================== About ================================== */
function AboutTab() {
  const [m, setM] = useState<Metrics | null>(null);
  useEffect(() => { getMetrics().then(setM).catch(() => setM(null)); }, []);

  return (
    <div className="formcard prose">
      <div className="abouthero"><Mascot src="/mascot-wave.png" size={84} float /><Mascot src="/mascot.png" size={84} /></div>
      <h2>How Kuza Connect works</h2>

      <h3>The problem</h3>
      <p>In under-resourced Kenyan schools, capable learners are routinely missed. This is most true for twice-exceptional children, who are gifted and also face a challenge such as ADHD or dyslexia, so they read as average. Timed, single-score tests hide the learners we most want to find.</p>

      <h3>What exists today (Phase 0 pilot)</h3>
      <p>A narrow, human-supervised slice: structured screening, teacher or parent nomination, context-adjusted spike-based scoring, and a review panel where a person decides on every flag. There is no automated diagnosis or placement. It currently runs on demo data, and the WhatsApp channel is in demo mode until a real provider is connected.</p>

      <h3>Three ways a child is found</h3>
      <ul>
        <li><b>Screening response.</b> The child answers five reasoning questions.</li>
        <li><b>Teacher or parent nomination.</b> A structured referral form.</li>
        <li><b>School-records signal.</b> A background job spots uneven grade patterns (spreadsheet only, no OCR yet).</li>
      </ul>

      <h3>The five reasoning domains</h3>
      <ul className="domainlist">
        {Object.entries(DOMAIN_LABELS).map(([k, v]) => (
          <li key={k}><Sym name={DOMAIN_SYM[k]} size={20} />{v}</li>
        ))}
      </ul>

      <h3>How Claude scoring works</h3>
      <p>Claude reads each open-ended answer and rates the reasoning from 0 to 100, with a short written evidence note, in English or Kiswahili. It scores reasoning and gives evidence. It does not diagnose, label, or decide.</p>

      <h3>Context adjustment, and no composite score</h3>
      <p>Scores are adjusted against the school resource tier, so a learner is not judged against a richer school baseline. Domains are never collapsed into one number. The system flags on the highest single-domain score and on unevenness, which is what surfaces twice-exceptional profiles.</p>

      <h3>Human review, audit, privacy</h3>
      <p>The AI flags and explains. A person records Advance, Hold, or Decline (Hold and Decline require a reason). Every flag-to-decision path is written to an append-only audit log. The data model stores no name, no diagnosis, and no health field. Consent is captured before screening.</p>

      <h3>What this system does not do</h3>
      <ul className="donts">
        <li>It does not diagnose ADHD, dyslexia, giftedness, or any medical condition.</li>
        <li>It does not auto-advance, auto-place, or auto-enrol any child.</li>
        <li>It does not compute a single combined score.</li>
        <li>It does not store names or health data, or decide without a human.</li>
      </ul>

      <h3>Live capabilities and current limits</h3>
      <div className="two">
        <div><b>Live now</b>
          <ul><li>Screening, Claude scoring, flags</li><li>Nomination form with 2e checklist</li><li>Human review, decisions, audit log</li><li>Context adjustment (tier lookup)</li><li>Records signal from spreadsheets</li></ul></div>
        <div><b>Not yet</b>
          <ul><li>Real WhatsApp (Twilio, demo only)</li><li>Trained context model (lookup only)</li><li>OCR of paper records</li><li>KEMIS or KNEC integration</li><li>Reviewer accounts and assignment</li></ul></div>
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
      <p className="muted small">Buildable on the current stack: reviewer assignment and status, fairness dashboards, exports, longitudinal tables, model-feedback capture. Needs a new provider or agreement: real WhatsApp (Twilio), KEMIS integration, notification channels.</p>
      <p className="muted small">This dashboard is the back-office tool for trained reviewers. The child-facing part is the WhatsApp chat. Phase 0 pilot build.</p>
    </div>
  );
}

const ROADMAP = [
  { title: "Real WhatsApp (Twilio)", external: true, effort: "M",
    value: "Reach real children in the field.",
    needs: "Twilio account and WhatsApp sender, approved message templates, webhook handling, consent and opt-out, retries, audit logs, and the provider adapter (already stubbed).",
    risks: "Delivery and consent handling, message cost, personal data in transit." },
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
