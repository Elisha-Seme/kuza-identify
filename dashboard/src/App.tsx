import { useEffect, useState } from "react";
import {
  ChecklistItem,
  FlaggedProfile,
  ScreeningItem,
  SchoolRow,
  getNominationForm,
  listFlagged,
  listItems,
  listSchools,
  recordDecision,
  runDemoScreening,
  submitNomination,
} from "./api";

type Tab = "review" | "nominate" | "questions" | "about";

/** Mascot image with graceful fallback — hides itself if the file isn't present
 * yet (drop PNGs into dashboard/public/: mascot.png, mascot-wave.png, mascot-thumb.png). */
function Mascot({ src, size = 60, className = "" }: { src: string; size?: number; className?: string }) {
  return (
    <img
      src={src}
      alt=""
      width={size}
      height={size}
      className={"mascotimg " + className}
      onError={(e) => (e.currentTarget.style.display = "none")}
    />
  );
}

const DOMAIN_LABELS: Record<string, string> = {
  numerical_reasoning: "Numeracy",
  verbal_reasoning: "Verbal",
  pattern_recognition: "Patterns",
  logical_reasoning: "Logic",
  working_memory: "Memory",
};

const PATHWAY_LABELS: Record<string, string> = {
  active_screening: "Did the screener",
  nomination: "Nominated by a teacher/parent",
  passive_signal: "Spotted in school records",
};

export function App() {
  const [tab, setTab] = useState<Tab>("review");

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <Mascot src="/mascot.png" size={64} className="mascot" />
          <div>
            <h1>Kuza Connect</h1>
            <p className="tagline">
              Finding gifted learners who’d otherwise be missed — AI flags, a human decides.
            </p>
          </div>
        </div>
      </header>

      <nav className="tabs">
        <button className={tab === "review" ? "on" : ""} onClick={() => setTab("review")}>
          🧑‍⚖️ Panel review
        </button>
        <button className={tab === "nominate" ? "on" : ""} onClick={() => setTab("nominate")}>
          📋 Nominate a child
        </button>
        <button className={tab === "questions" ? "on" : ""} onClick={() => setTab("questions")}>
          ❓ Screening questions
        </button>
        <button className={tab === "about" ? "on" : ""} onClick={() => setTab("about")}>
          💡 How it works
        </button>
      </nav>

      <main className="content">
        {tab === "review" && <ReviewTab />}
        {tab === "nominate" && <NominateTab />}
        {tab === "questions" && <QuestionsTab />}
        {tab === "about" && <AboutTab />}
      </main>
    </div>
  );
}

/* ------------------------------- Review ---------------------------------- */
function ReviewTab() {
  const [profiles, setProfiles] = useState<FlaggedProfile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [reviewerId, setReviewerId] = useState("reviewer-1");
  const [selected, setSelected] = useState<string | null>(null);
  const [demoMsg, setDemoMsg] = useState<string | null>(null);

  async function refresh() {
    try {
      setProfiles(await listFlagged());
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    refresh();
  }, []);

  async function runDemo() {
    const token = window.localStorage.getItem("kuza_admin_token") ||
      window.prompt("Enter the ADMIN_TOKEN to run a live demo screening:") || "";
    if (!token) return;
    window.localStorage.setItem("kuza_admin_token", token);
    setDemoMsg("Running a screening through the scorer…");
    try {
      const r = await runDemoScreening(token);
      setDemoMsg(`New profile created (scored by ${r.scored_by}). Refreshing…`);
      await refresh();
    } catch (e) {
      setDemoMsg("Demo failed: " + String(e));
    }
  }

  const current = profiles.find((p) => p.session_id === selected) || profiles[0];

  return (
    <div>
      <div className="rowbar">
        <p className="lead">
          These are children the system flagged for a human to look at. Pick one to see the
          evidence, then record a decision.
        </p>
        <div className="controls">
          Reviewer:&nbsp;<input value={reviewerId} onChange={(e) => setReviewerId(e.target.value)} />
          <button onClick={refresh}>Refresh</button>
          <button className="ghost" onClick={runDemo}>▶ Run demo screening</button>
        </div>
      </div>
      {demoMsg && <div className="banner">{demoMsg}</div>}
      {error && <div className="error">Couldn’t reach the API: {error}</div>}

      <div className="legend">
        <strong>How each child was found:</strong>
        <span className="pill active_screening">Did the screener</span>
        <span className="pill nomination">Nominated</span>
        <span className="pill passive_signal">Spotted in records</span>
      </div>

      <div className="split">
        <aside>
          <h3>Flagged children ({profiles.length})</h3>
          {profiles.length === 0 && <p className="muted">None yet.</p>}
          <ul className="cards">
            {profiles.map((p) => (
              <li
                key={p.session_id}
                className={current?.session_id === p.session_id ? "active" : ""}
                onClick={() => setSelected(p.session_id)}
              >
                <span className={`pill ${p.learner_source}`}>
                  {PATHWAY_LABELS[p.learner_source] ?? p.learner_source}
                </span>
                <div className="cardline">
                  <code>{p.learner_id.slice(0, 8)}</code>
                  <span className="muted">{p.flags.length} flag(s)</span>
                  {p.existing_decision && <span className="decided">→ {p.existing_decision}</span>}
                </div>
              </li>
            ))}
          </ul>
        </aside>
        <section className="panelcard">
          {current ? (
            <ProfileView key={current.session_id} profile={current} reviewerId={reviewerId} onDecided={refresh} />
          ) : (
            <p className="muted">Select a child on the left.</p>
          )}
        </section>
      </div>
    </div>
  );
}

function plainSummary(p: FlaggedProfile): string {
  const top = [...p.profile].sort((a, b) => b.adjusted_score - a.adjusted_score)[0];
  const low = [...p.profile].sort((a, b) => a.adjusted_score - b.adjusted_score)[0];
  if (!top || !low) return "Flagged for review.";
  const t = DOMAIN_LABELS[top.domain] ?? top.domain;
  const l = DOMAIN_LABELS[low.domain] ?? low.domain;
  return `Strongest in ${t} (${top.adjusted_score}/100), weakest in ${l} (${low.adjusted_score}/100) — an uneven profile worth a look.`;
}

function ProfileView({
  profile,
  reviewerId,
  onDecided,
}: {
  profile: FlaggedProfile;
  reviewerId: string;
  onDecided: () => void;
}) {
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function decide(decision: "advance" | "hold" | "decline") {
    setBusy(true);
    setMsg(null);
    try {
      await recordDecision(profile.session_id, reviewerId, decision, notes);
      setMsg(`Recorded: ${decision}`);
      onDecided();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2>
        Child <code>{profile.learner_id.slice(0, 8)}</code>{" "}
        <span className={`pill ${profile.learner_source}`}>
          {PATHWAY_LABELS[profile.learner_source] ?? profile.learner_source}
        </span>
      </h2>
      <p className="summary">{plainSummary(profile)}</p>

      <section>
        <h3>Why it was flagged</h3>
        {profile.flags.map((f) => (
          <div className="flag" key={f.id}>
            <strong>{f.rule_id.includes("spike") ? "A standout spike in one skill" : "Very uneven across skills (2e pattern)"}</strong>
            <div className="muted">{f.rule_description}</div>
          </div>
        ))}
      </section>

      <section>
        <h3>Score in each thinking skill</h3>
        <p className="muted">
          Skills stay separate — there’s no single combined score. “Adjusted” fairly bumps the raw
          score using the school’s resource level.
        </p>
        <div className="tablewrap">
          <table>
            <thead>
              <tr><th>Skill</th><th>Raw</th><th>×Factor</th><th>Adjusted</th><th>What the scorer saw</th></tr>
            </thead>
            <tbody>
              {profile.profile.map((d) => (
                <tr key={d.domain}>
                  <td>{DOMAIN_LABELS[d.domain] ?? d.domain}</td>
                  <td>{d.raw_score}</td>
                  <td>{d.adjustment_factor.toFixed(2)}</td>
                  <td><strong>{d.adjusted_score}</strong></td>
                  <td className="evidence">{d.evidence_text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="two">
        <div>
          <h3>Nomination notes</h3>
          <p>2e warning signs ticked: <strong>{profile.nomination_amber_flags}</strong> <span className="muted">(context, not a score)</span></p>
        </div>
        <div>
          <h3>Records signal</h3>
          {profile.candidate_signals.length === 0 ? <p className="muted">None.</p> :
            profile.candidate_signals.map((s) => (
              <div key={s.id} className="muted">{s.signal_type} · {s.confidence} confidence (advisory only)</div>
            ))}
        </div>
      </section>

      <section className="decision">
        <h3>Your decision</h3>
        {profile.existing_decision && <p className="muted">Last recorded: <strong>{profile.existing_decision}</strong></p>}
        <textarea placeholder="Notes (optional)…" value={notes} onChange={(e) => setNotes(e.target.value)} />
        <div className="buttons">
          <button disabled={busy} className="advance" onClick={() => decide("advance")}>Advance ✓</button>
          <button disabled={busy} className="hold" onClick={() => decide("hold")}>Hold</button>
          <button disabled={busy} className="decline" onClick={() => decide("decline")}>Decline</button>
        </div>
        {msg && <p className="msg">{msg}</p>}
      </section>
    </div>
  );
}

/* ------------------------------ Nominate --------------------------------- */
function NominateTab() {
  const [form, setForm] = useState<ChecklistItem[]>([]);
  const [schools, setSchools] = useState<SchoolRow[]>([]);
  const [schoolId, setSchoolId] = useState("");
  const [role, setRole] = useState<"teacher" | "parent">("teacher");
  const [answers, setAnswers] = useState<Record<string, boolean>>({});
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getNominationForm().then(setForm).catch((e) => setError(String(e)));
    listSchools().then((s) => { setSchools(s); if (s[0]) setSchoolId(s[0].id); }).catch(() => {});
  }, []);

  async function submit() {
    setResult(null); setError(null);
    try {
      const r = await submitNomination({
        school_id: schoolId,
        nominator_role: role,
        checklist_responses: answers,
        guardian_identifier: role === "parent" ? "web-parent" : undefined,
      });
      setResult(`Nomination saved. Twice-exceptional warning signs ticked: ${r.amber_flag_count}. The child now awaits screening before the panel sees a decision.`);
      setAnswers({});
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div className="formcard">
      <h2>Nominate a child</h2>
      <p className="lead">A teacher or parent flags a child who seems bright. ⚠️ marks the
        “twice-exceptional” signs — gifted but also struggling in a way that hides it.</p>

      <label>School
        <select value={schoolId} onChange={(e) => setSchoolId(e.target.value)}>
          {schools.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.tier})</option>)}
        </select>
      </label>
      <label>I am a
        <select value={role} onChange={(e) => setRole(e.target.value as any)}>
          <option value="teacher">Teacher</option>
          <option value="parent">Parent / guardian</option>
        </select>
      </label>

      <div className="checklist">
        {form.map((c) => (
          <label key={c.key} className={"check " + (c.amber_flag ? "amber" : "")}>
            <input type="checkbox" checked={!!answers[c.key]}
              onChange={(e) => setAnswers({ ...answers, [c.key]: e.target.checked })} />
            <span>{c.amber_flag ? "⚠️ " : ""}{c.prompt_en}</span>
          </label>
        ))}
      </div>

      <button className="advance" disabled={!schoolId} onClick={submit}>Submit nomination</button>
      {result && (
        <div className="banner ok withmascot">
          <Mascot src="/mascot-thumb.png" size={54} />
          <span>{result}</span>
        </div>
      )}
      {error && <div className="error">{error}</div>}
    </div>
  );
}

/* --------------------------- Screening questions -------------------------- */
function QuestionsTab() {
  const [items, setItems] = useState<ScreeningItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { listItems().then(setItems).catch((e) => setError(String(e))); }, []);

  return (
    <div className="formcard">
      <h2>The screening questions</h2>
      <p className="lead">A child answers these five short questions — in real life over a WhatsApp
        chat, in English or Kiswahili. There are no trick “right answers”: the scorer rewards the
        <em> reasoning</em> a child shows, not neat handwriting or perfect arithmetic.</p>
      {error && <div className="error">{error}</div>}
      <ol className="questions">
        {items.map((it) => (
          <li key={it.id}>
            <span className="pill neutral">{DOMAIN_LABELS[it.domain] ?? it.domain}</span>
            <p className="qen">{it.prompt.en}</p>
            <p className="qsw">🇰🇪 {it.prompt.sw}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* -------------------------------- About ---------------------------------- */
function AboutTab() {
  return (
    <div className="formcard prose">
      <div className="abouthero">
        <Mascot src="/mascot-wave.png" size={96} />
        <Mascot src="/mascot.png" size={96} />
      </div>
      <h2>How Kuza Connect works</h2>
      <p><strong>The goal:</strong> find bright children in under-resourced Kenyan schools who normally
        get missed — especially “twice-exceptional” kids who are gifted <em>and</em> have something
        like ADHD or dyslexia, so they look average and nobody notices.</p>

      <h3>A child’s journey</h3>
      <ol className="steps">
        <li><strong>Get noticed</strong> — three ways in:
          <ul>
            <li><span className="pill active_screening">Screener</span> the child answers 5 puzzles over WhatsApp.</li>
            <li><span className="pill nomination">Nomination</span> a teacher/parent fills the form.</li>
            <li><span className="pill passive_signal">Records</span> a background job spots odd patterns in school grades.</li>
          </ul>
        </li>
        <li><strong>AI scores the answers</strong> — Claude rates the <em>reasoning</em> per skill (0–100) and writes a note explaining why.</li>
        <li><strong>Look for a spike, not an average</strong> — the system never blends skills into one number. It flags a child when one skill is very high, or when the skills are very uneven (the tell-tale sign of a gifted-but-struggling child).</li>
        <li><strong>A human decides</strong> — the AI only flags and explains. On the <em>Panel review</em> tab a person clicks Advance / Hold / Decline. Every flag→decision is logged permanently.</li>
      </ol>

      <h3>Two fairness rules built in</h3>
      <ul>
        <li><strong>Context adjustment:</strong> a child from a poorer school is scored against that tougher baseline, not a rich school’s — so scores get a fair bump.</li>
        <li><strong>Privacy by design:</strong> no name, no diagnosis, no health label is ever stored. Support is triggered by <em>patterns</em>, never by a medical label.</li>
      </ul>
      <p className="muted">This dashboard is the back-office tool for trained reviewers. The child-facing
        part is the WhatsApp chat (not shown here). This is the Phase 0 pilot build.</p>
    </div>
  );
}
