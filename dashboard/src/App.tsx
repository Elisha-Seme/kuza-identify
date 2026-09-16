import { useEffect, useMemo, useState } from "react";
import {
  ChecklistItem,
  FlaggedProfile,
  Health,
  Metrics,
  ScreeningItem,
  SchoolRow,
  getHealth,
  getMetrics,
  getNominationForm,
  listFlagged,
  listItems,
  listSchools,
  recordDecision,
  runDemoScreening,
  submitNomination,
} from "./api";

type Tab = "about" | "review" | "nominate" | "questions";

const DOMAIN_LABELS: Record<string, string> = {
  numerical_reasoning: "Numeracy",
  verbal_reasoning: "Verbal",
  pattern_recognition: "Patterns",
  logical_reasoning: "Logic",
  working_memory: "Memory",
};

// Clearer source labels (brief: replace "Did the screener" → "Screening response").
const SOURCE_LABELS: Record<string, string> = {
  active_screening: "Screening response",
  nomination: "Teacher/parent nomination",
  passive_signal: "School-records signal",
};

const DECISION_HELP: Record<string, string> = {
  advance:
    "Advance — the child moves forward for support (mentor matching, Layer 2). Recorded permanently in the audit log.",
  hold:
    "Hold — no decision yet; the child stays in the queue pending more evidence or a second reviewer. A reason is required.",
  decline:
    "Decline — the child is not advanced from this screening. A reason is required. Reversible only by a later review.",
};

function statusOf(p: FlaggedProfile): "awaiting" | "advanced" | "held" | "declined" {
  if (!p.existing_decision) return "awaiting";
  return p.existing_decision as any;
}
const STATUS_LABELS: Record<string, string> = {
  awaiting: "Awaiting review",
  advanced: "Advanced",
  held: "Held",
  declined: "Declined",
};

function Mascot({ src, size = 60, className = "" }: { src: string; size?: number; className?: string }) {
  return (
    <img src={src} alt="" width={size} height={size} className={"mascotimg " + className}
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
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  const TABS: { id: Tab; label: string; purpose: string }[] = [
    { id: "about", label: "💡 How it works", purpose: "Start here — what this pilot is" },
    { id: "review", label: "🧑‍⚖️ Panel review", purpose: "Review flagged children & decide" },
    { id: "nominate", label: "📋 Nominate a child", purpose: "Teacher / parent referral" },
    { id: "questions", label: "❓ Screening questions", purpose: "The 5 questions a child answers" },
  ];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <Mascot src="/mascot.png" size={64} className="mascot" />
          <div>
            <h1>Kuza Connect</h1>
            <p className="tagline">Finding gifted learners who’d otherwise be missed — AI flags, a human decides.</p>
          </div>
        </div>
        {health && (
          <div className={"provider " + (health.llm_scoring === "live" ? "live" : "mock")}>
            Scoring: <strong>{health.llm_scoring === "live" ? "Live Claude" : "Mock (demo)"}</strong>
            <span className="sep">·</span>
            WhatsApp: <strong>{health.whatsapp_provider === "mock" ? "Mock (not connected)" : health.whatsapp_provider}</strong>
          </div>
        )}
      </header>

      {offline && <div className="offline">You appear to be offline — showing what’s already loaded. Reconnect to refresh.</div>}

      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "on" : ""} onClick={() => setTab(t.id)} title={t.purpose}>
            {t.label}
          </button>
        ))}
      </nav>
      <p className="tabpurpose">{TABS.find((t) => t.id === tab)?.purpose}</p>

      <main className="content">
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
      window.prompt("Enter the ADMIN_TOKEN to run a live demo screening:") || "";
    if (!token) return;
    localStorage.setItem("kuza_admin_token", token);
    setDemoMsg("Running a screening through the scorer…");
    try { const r = await runDemoScreening(token); setDemoMsg(`New profile created (scored by ${r.scored_by}). Refreshed.`); await refresh(); }
    catch (e) { setDemoMsg("Demo failed: " + String(e)); }
  }

  const filtered = useMemo(() => {
    if (!profiles) return [];
    return profiles.filter((p) => {
      if (statusFilter !== "all" && statusOf(p) !== statusFilter) return false;
      if (sourceFilter !== "all" && p.learner_source !== sourceFilter) return false;
      if (search && !p.learner_id.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [profiles, statusFilter, sourceFilter, search]);

  const current = filtered.find((p) => p.session_id === selected) || filtered[0];

  return (
    <div>
      <div className="rowbar">
        <p className="lead">The operational queue: children the system flagged for a human to review. Filter, open one, read the evidence, then record a decision.</p>
        <div className="controls">
          Reviewer:&nbsp;<input value={reviewerId} onChange={(e) => setReviewerId(e.target.value)} />
          <button onClick={refresh}>Refresh</button>
          <button className="ghost" onClick={runDemo}>▶ Run demo screening</button>
        </div>
      </div>
      {health && health.whatsapp_provider === "mock" && (
        <div className="banner warn">⚠️ Mock mode: no real WhatsApp provider is connected. Screening data here is demo/seed data.</div>
      )}
      {demoMsg && <div className="banner">{demoMsg}</div>}
      {error && <div className="error">Couldn’t reach the API: {error}</div>}

      <div className="filters">
        <label>Status
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">All</option>
            <option value="awaiting">Awaiting review</option>
            <option value="advanced">Advanced</option>
            <option value="held">Held</option>
            <option value="declined">Declined</option>
          </select>
        </label>
        <label>Source
          <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
            <option value="all">All</option>
            <option value="active_screening">Screening response</option>
            <option value="nomination">Nomination</option>
            <option value="passive_signal">Records signal</option>
          </select>
        </label>
        <label>Find learner (anonymised id)
          <input placeholder="e.g. 7a381663" value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
      </div>

      {profiles === null ? (
        <div className="loading">Loading queue…</div>
      ) : (
        <div className="split">
          <aside>
            <h3>Queue ({filtered.length})</h3>
            {filtered.length === 0 && <p className="muted">No children match these filters.</p>}
            <ul className="cards">
              {filtered.map((p) => (
                <li key={p.session_id} className={current?.session_id === p.session_id ? "active" : ""} onClick={() => setSelected(p.session_id)}>
                  <div className="cardtop">
                    <span className={`badge ${statusOf(p)}`}>{STATUS_LABELS[statusOf(p)]}</span>
                    <span className={`pill ${p.learner_source}`}>{SOURCE_LABELS[p.learner_source] ?? p.learner_source}</span>
                  </div>
                  <div className="cardline">
                    <code>{p.learner_id.slice(0, 8)}</code>
                    <span className="muted">{p.flags.length} flag(s) · {p.received_at ? new Date(p.received_at).toLocaleDateString() : "—"}</span>
                  </div>
                </li>
              ))}
            </ul>
          </aside>
          <section className="panelcard">
            {current ? <ProfileView key={current.session_id} profile={current} reviewerId={reviewerId} onDecided={refresh} />
              : <p className="muted">No child selected.</p>}
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
  return `Strongest in ${DOMAIN_LABELS[top.domain] ?? top.domain} (${top.adjusted_score}/100), weakest in ${DOMAIN_LABELS[low.domain] ?? low.domain} (${low.adjusted_score}/100) — an uneven profile worth a human look.`;
}

function ProfileView({ profile, reviewerId, onDecided }: { profile: FlaggedProfile; reviewerId: string; onDecided: () => void; }) {
  const [pending, setPending] = useState<null | "advance" | "hold" | "decline">(null);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const completeness = `${profile.responses_count}/${profile.expected_items} answered`;

  async function confirm() {
    if (!pending) return;
    if ((pending === "hold" || pending === "decline") && notes.trim().length === 0) {
      setMsg("A written reason is required to Hold or Decline."); return;
    }
    setBusy(true); setMsg(null);
    try { await recordDecision(profile.session_id, reviewerId, pending, notes); setMsg(`Recorded: ${pending}`); setPending(null); setNotes(""); onDecided(); }
    catch (e) { setMsg(String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <div className="detailhead">
        <h2>Child <code>{profile.learner_id.slice(0, 8)}</code></h2>
        <span className={`badge ${statusOf(profile)}`}>{STATUS_LABELS[statusOf(profile)]}</span>
      </div>
      <p className="metaline">
        <span className={`pill ${profile.learner_source}`}>{SOURCE_LABELS[profile.learner_source] ?? profile.learner_source}</span>
        {" "}· Received {profile.received_at ? new Date(profile.received_at).toLocaleString() : "—"}
        {" "}· Channel {profile.channel}
      </p>
      <p className="summary">{plainSummary(profile)}</p>

      <section>
        <h3>Evidence quality</h3>
        <div className="quality">
          <span>Language: <strong>{profile.language === "sw" ? "Kiswahili" : "English"}</strong></span>
          <span>Completeness: <strong>{completeness}</strong></span>
          <span>Scored by: <strong className={profile.scored_live ? "ok" : "warn"}>{profile.scored_live ? "Live Claude" : "Mock / seed"}</strong></span>
        </div>
        <p className="muted small">What could change this assessment: a fuller session, a second-language re-check, or a reviewer noticing a misread question. Scores rate <em>reasoning</em>, not correctness — treat a single low score cautiously.</p>
      </section>

      <section>
        <h3>Why it was flagged</h3>
        {profile.flags.map((f) => (
          <div className="flag" key={f.id}>
            <strong>{f.rule_id.includes("spike") ? "A standout spike in one skill" : "Very uneven across skills (a pattern that can indicate twice-exceptional — needs human review, not a diagnosis)"}</strong>
            <div className="muted">{f.rule_description}</div>
          </div>
        ))}
      </section>

      <section>
        <h3>Score in each thinking skill</h3>
        <p className="muted small">Skills stay separate — there is no single combined score. “Adjusted” applies the school’s resource-tier factor for fairness.</p>
        <div className="tablewrap">
          <table>
            <thead><tr><th>Skill</th><th>Raw</th><th>×Factor</th><th>Adjusted</th><th>What the scorer saw</th></tr></thead>
            <tbody>
              {profile.profile.map((d) => (
                <tr key={d.domain}>
                  <td>{DOMAIN_LABELS[d.domain] ?? d.domain}</td>
                  <td>{d.raw_score}</td><td>{d.adjustment_factor.toFixed(2)}</td>
                  <td><strong>{d.adjusted_score}</strong></td>
                  <td className="evidence">{d.evidence_text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="two">
        <div><h3>Nomination notes</h3><p>2e warning signs ticked: <strong>{profile.nomination_amber_flags}</strong> <span className="muted">(context, not a score)</span></p></div>
        <div><h3>Records signal</h3>{profile.candidate_signals.length === 0 ? <p className="muted">None.</p> :
          profile.candidate_signals.map((s) => <div key={s.id} className="muted">{s.signal_type} · {s.confidence} confidence (advisory only)</div>)}</div>
      </section>

      {profile.review_history.length > 0 && (
        <section>
          <h3>Decision history (audit)</h3>
          <ul className="history">
            {profile.review_history.map((r, i) => (
              <li key={i}><span className={`badge ${r.decision}`}>{r.decision}</span> by {r.reviewer_id} · {new Date(r.decided_at).toLocaleString()}{r.notes ? ` — “${r.notes}”` : ""}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="decision">
        <h3>Your decision</h3>
        <div className="buttons">
          <button disabled={busy} className="advance" onClick={() => { setPending("advance"); setMsg(null); }}>Advance ✓</button>
          <button disabled={busy} className="hold" onClick={() => { setPending("hold"); setMsg(null); }}>Hold</button>
          <button disabled={busy} className="decline" onClick={() => { setPending("decline"); setMsg(null); }}>Decline</button>
        </div>
        {msg && <p className="msg">{msg}</p>}
      </section>

      {pending && (
        <div className="modalback" onClick={() => setPending(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Confirm: {pending}</h3>
            <p>{DECISION_HELP[pending]}</p>
            <label className="modallabel">Reason / notes {(pending === "hold" || pending === "decline") && <span className="req">(required)</span>}
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Why this decision?" />
            </label>
            <div className="buttons">
              <button className={pending} disabled={busy} onClick={confirm}>Confirm {pending}</button>
              <button onClick={() => setPending(null)}>Cancel</button>
            </div>
            {msg && <p className="msg">{msg}</p>}
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
    try {
      const d = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null");
      if (d) { setAnswers(d.answers || {}); setObservation(d.observation || ""); setAgeRange(d.ageRange || ""); setRole(d.role || "teacher"); }
    } catch { /* ignore */ }
  }, []);

  function saveDraft() {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({ answers, observation, ageRange, role }));
    setError(null); setResult(null);
    alert("Draft saved on this device — you can continue later.");
  }

  async function submit() {
    setResult(null); setError(null);
    if (!consent) { setError("Please confirm consent to nominate before submitting."); return; }
    try {
      const r = await submitNomination({
        school_id: schoolId, nominator_role: role,
        // Free-text observation + age range are stored inside the structured JSONB
        // field — no schema change, still no free-form personal identifiers requested.
        checklist_responses: { ...answers, _observation: observation || undefined, _age_range: ageRange || undefined },
        guardian_identifier: consent ? (role === "parent" ? "web-parent-consent" : "web-teacher-consent") : undefined,
      });
      setResult({ id: r.nomination_id, amber: r.amber_flag_count });
      setAnswers({}); setObservation(""); setAgeRange(""); setConsent(false);
      localStorage.removeItem(DRAFT_KEY);
    } catch (e) { setError(String(e)); }
  }

  return (
    <div className="formcard">
      <h2>Nominate a child</h2>
      <p className="lead">A teacher or parent flags a child who seems bright. ⚠️ marks “twice-exceptional” signs — gifted but also struggling in a way that hides it. This is a <em>referral for screening</em>, never a diagnosis.</p>

      <div className="safeguard">
        <strong>🛡️ Safeguarding & privacy:</strong> do not enter the child’s name or any medical information. Nominate only children you are responsible for or guardian to. A nomination invites the child to a short screening; a human panel reviews everything before any decision.
      </div>

      <label>School
        <select value={schoolId} onChange={(e) => setSchoolId(e.target.value)}>
          {schools.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.tier})</option>)}
        </select>
      </label>
      <label>I am a
        <select value={role} onChange={(e) => setRole(e.target.value as any)}>
          <option value="teacher">Teacher</option><option value="parent">Parent / guardian</option>
        </select>
      </label>
      <label>Approximate class / age range (optional)
        <input value={ageRange} onChange={(e) => setAgeRange(e.target.value)} placeholder="e.g. Grade 4, or ~9–10 years" />
      </label>

      <div className="checklist">
        {form.map((c) => (
          <label key={c.key} className={"check " + (c.amber_flag ? "amber" : "")}>
            <input type="checkbox" checked={!!answers[c.key]} onChange={(e) => setAnswers({ ...answers, [c.key]: e.target.checked })} />
            <span>{c.amber_flag ? "⚠️ " : ""}{c.prompt_en}</span>
          </label>
        ))}
      </div>

      <label>Anything you’ve observed (optional, no names)
        <textarea value={observation} onChange={(e) => setObservation(e.target.value)} placeholder="e.g. explains ideas to classmates but freezes on written tests" />
      </label>

      <label className="consent">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>I confirm I have the appropriate consent to nominate this child for screening.</span>
      </label>

      <div className="buttons">
        <button className="advance" disabled={!schoolId || !consent} onClick={submit}>Submit nomination</button>
        <button className="ghost" onClick={saveDraft}>Save draft</button>
      </div>

      {result && (
        <div className="banner ok withmascot">
          <Mascot src="/mascot-thumb.png" size={54} />
          <span>Nomination saved. Twice-exceptional signs ticked: <strong>{result.amber}</strong>. Tracking ID: <code>{result.id.slice(0, 8)}</code>. The child now awaits screening before the panel records a decision.</span>
        </div>
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
      <p className="lead">A child answers these five short questions — in real life over WhatsApp, in English or Kiswahili. There are no trick “right answers”: the scorer rewards the <em>reasoning</em> shown, not neat handwriting or perfect arithmetic.</p>
      {error && <div className="error">{error}</div>}
      {items === null ? <div className="loading">Loading questions…</div> : (
        <ol className="questions">
          {items.map((it) => (
            <li key={it.id}>
              <span className="pill neutral">{DOMAIN_LABELS[it.domain] ?? it.domain}</span>
              <p className="qen">{it.prompt.en}</p>
              <p className="qsw">🇰🇪 {it.prompt.sw}</p>
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
      <div className="abouthero">
        <Mascot src="/mascot-wave.png" size={92} />
        <Mascot src="/mascot.png" size={92} />
      </div>
      <h2>How Kuza Connect works</h2>

      <h3>The problem</h3>
      <p>In under-resourced Kenyan schools, capable learners are routinely missed — especially <strong>twice-exceptional</strong> children who are gifted <em>and</em> face a challenge like ADHD or dyslexia, so they read as “average.” Timed, single-score tests hide exactly the children we most want to find.</p>

      <h3>What exists today (Phase 0 pilot)</h3>
      <p>A narrow, human-supervised slice: structured <strong>screening</strong> + <strong>teacher/parent nomination</strong>, context-adjusted spike-based scoring, and a review panel where a person decides on <em>every</em> flag. No automated diagnosis or placement. Currently running with demo data; the WhatsApp channel is in <strong>mock mode</strong> until a real provider is connected.</p>

      <h3>Three ways a child is found</h3>
      <ul>
        <li><span className="pill active_screening">Screening response</span> the child answers 5 reasoning puzzles.</li>
        <li><span className="pill nomination">Teacher/parent nomination</span> a structured referral form.</li>
        <li><span className="pill passive_signal">School-records signal</span> a background job spots uneven grade patterns (spreadsheet only, no OCR yet).</li>
      </ul>

      <h3>The five reasoning domains</h3>
      <p>Numeracy · Verbal · Patterns · Logic · Memory — scored <strong>independently</strong>.</p>

      <h3>How Claude scoring works</h3>
      <p>Claude reads each open-ended answer and rates the <strong>reasoning</strong> (0–100) with a short written <strong>evidence</strong> note, in English or Kiswahili. It scores reasoning and gives evidence — it does <strong>not</strong> diagnose, label, or decide.</p>

      <h3>Context adjustment & no composite score</h3>
      <p>Scores are adjusted against the school’s resource tier so a child isn’t judged against a richer school’s baseline. Domains are never collapsed into one number — the system flags on the <em>maximum</em> per-domain spike and on <em>unevenness</em>, which is what surfaces twice-exceptional profiles.</p>

      <h3>Human review, audit, privacy</h3>
      <p>AI only flags + explains; a human records <strong>Advance / Hold / Decline</strong> (Hold and Decline require a reason). Every flag→decision path is written to an <strong>append-only audit log</strong>. The data model stores <strong>no name, no diagnosis, no health field</strong>; consent is captured before screening.</p>

      <h3>What this system explicitly does NOT do</h3>
      <ul className="donts">
        <li>It does <strong>not</strong> diagnose ADHD, dyslexia, giftedness, or any medical condition.</li>
        <li>It does <strong>not</strong> auto-advance, auto-place, or auto-enrol any child.</li>
        <li>It does <strong>not</strong> compute a single IQ-like composite score.</li>
        <li>It does <strong>not</strong> store names or health data, or make decisions without a human.</li>
      </ul>

      <h3>Live capabilities vs limitations</h3>
      <div className="two">
        <div><strong>Live now</strong>
          <ul><li>Screening → Claude scoring → flags</li><li>Nomination form (2e checklist)</li><li>Human review + decisions + audit log</li><li>Context adjustment (tier lookup)</li><li>Records signal from spreadsheets</li></ul>
        </div>
        <div><strong>Not yet / limits</strong>
          <ul><li>Real WhatsApp (mock only)</li><li>Trained context model (lookup only)</li><li>OCR of paper records</li><li>KEMIS / KNEC integration</li><li>Reviewer accounts & assignment</li></ul>
        </div>
      </div>

      {m && (
        <>
          <h3>Live pilot numbers</h3>
          <div className="stats">
            {Object.entries(m.funnel).map(([k, v]) => (
              <div className="stat" key={k}><div className="statv">{v}</div><div className="statk">{k.replace(/_/g, " ")}</div></div>
            ))}
          </div>
          <p className="muted small">Flag rate by language: {Object.entries(m.slices.language || {}).map(([k, s]) => `${k} ${s.flagged}/${s.sessions}`).join(" · ") || "—"}. Deeper fairness (reviewer agreement, false pos/neg) needs labelled ground truth — a Phase-2 item, not invented here.</p>
        </>
      )}

      <h3>What we can add next (roadmap)</h3>
      <p className="muted small">Each item lists value · dependencies · risks · effort. “Effort” is rough: S/M/L. Items needing new providers or agreements are marked ⛔ external.</p>
      <div className="tablewrap">
        <table className="roadmap">
          <thead><tr><th>Capability</th><th>Value</th><th>Needs</th><th>Risks</th><th>Effort</th></tr></thead>
          <tbody>
            <tr><td>Real WhatsApp ⛔</td><td>Reach real children in the field</td><td>Provider (Africa’s Talking/Twilio), WhatsApp Business number, template approval, secrets; backend provider adapter (already stubbed)</td><td>Delivery/consent handling, message costs, PII in transit</td><td>M</td></tr>
            <tr><td>KEMIS data ⛔ (discovery)</td><td>Find never-nominated children from existing records</td><td><strong>First confirm the system & that an authorised API/route exists</strong> — data model, auth, consent basis, rate limits, MOU. No endpoint assumed. Interim: CSV/SFTP/manual import with audit logs via the existing adapter interface</td><td>No public write API today; legal/consent; re-encoding teacher bias</td><td>L</td></tr>
            <tr><td>School/teacher accounts + roles</td><td>Real logins, scoped access</td><td>Auth system, users/roles tables, session mgmt</td><td>Access control, password/security</td><td>L</td></tr>
            <tr><td>Reviewer queue: assignment + “In review”</td><td>Coordinate multiple reviewers</td><td>New status/assignment columns (beyond current schema), migration</td><td>Schema change vs. locked model</td><td>M</td></tr>
            <tr><td>Fairness & calibration dashboards</td><td>Prove equity claim</td><td>Labelled ground truth, reviewer-agreement capture, more metrics</td><td>Misleading stats on tiny samples</td><td>M</td></tr>
            <tr><td>Longitudinal support tracking</td><td>Follow outcomes over time</td><td>Outcome/follow-up tables, Layer-2 link</td><td>Long-term data governance</td><td>L</td></tr>
            <tr><td>Human-reviewed model recalibration</td><td>Improve scoring from reviewer feedback</td><td>Feedback capture, prompt/version mgmt, eval set</td><td>Feedback loops encoding bias</td><td>M</td></tr>
            <tr><td>Exports / reporting</td><td>Share de-identified stats with partners</td><td>Export endpoints, aggregation, redaction</td><td>Re-identification risk</td><td>S–M</td></tr>
            <tr><td>Notifications & escalation</td><td>Timely reviewer action</td><td>Email/SMS integration, rules</td><td>Alert fatigue, PII in notifications</td><td>S–M</td></tr>
          </tbody>
        </table>
      </div>
      <p className="muted small">Buildable on the current stack (no new provider): reviewer assignment/status, fairness dashboards, exports, longitudinal tables, model-feedback capture. Requires new providers or agreements (⛔): real WhatsApp, KEMIS integration, and notification channels.</p>
      <p className="muted">This dashboard is the back-office tool for trained reviewers; the child-facing part is the WhatsApp chat. Phase 0 pilot build.</p>
    </div>
  );
}
