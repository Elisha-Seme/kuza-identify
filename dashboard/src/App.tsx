import { useEffect, useState } from "react";
import {
  FlaggedProfile,
  listFlagged,
  recordDecision,
} from "./api";

// Panel Review Dashboard (spec Section 4). Minimal but functional: list flagged
// profiles, show the per-domain evidence + flags + nomination / passive context,
// and let a reviewer record a decision. The decision is written server-side only
// (Section 3.6) and appended to the immutable audit log.

export function App() {
  const [profiles, setProfiles] = useState<FlaggedProfile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [reviewerId, setReviewerId] = useState("reviewer-1");
  const [selected, setSelected] = useState<string | null>(null);

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

  const current = profiles.find((p) => p.session_id === selected) || profiles[0];

  return (
    <div className="layout">
      <header>
        <h1>Kuza Connect — Panel Review</h1>
        <div className="reviewer">
          Reviewer:&nbsp;
          <input
            value={reviewerId}
            onChange={(e) => setReviewerId(e.target.value)}
          />
          <button onClick={refresh}>Refresh</button>
        </div>
      </header>

      {error && <div className="error">API error: {error}</div>}

      <div className="body">
        <aside>
          <h2>Flagged profiles ({profiles.length})</h2>
          {profiles.length === 0 && <p className="muted">None yet. Run the seed script.</p>}
          <ul>
            {profiles.map((p) => (
              <li
                key={p.session_id}
                className={current?.session_id === p.session_id ? "active" : ""}
                onClick={() => setSelected(p.session_id)}
              >
                <span className={`pill ${p.learner_source}`}>{p.learner_source}</span>
                <code>{p.session_id.slice(0, 8)}</code>
                <span className="flagcount">{p.flags.length} flag(s)</span>
                {p.existing_decision && (
                  <span className="decided">→ {p.existing_decision}</span>
                )}
              </li>
            ))}
          </ul>
        </aside>

        <main>
          {current ? (
            <ProfileView
              key={current.session_id}
              profile={current}
              reviewerId={reviewerId}
              onDecided={refresh}
            />
          ) : (
            <p className="muted">Select a flagged profile.</p>
          )}
        </main>
      </div>
    </div>
  );
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
      setMsg(`Recorded decision: ${decision}`);
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
        Learner <code>{profile.learner_id.slice(0, 8)}</code>{" "}
        <span className={`pill ${profile.learner_source}`}>{profile.learner_source}</span>
      </h2>
      <p className="muted">
        Session {profile.session_id} · School {profile.school_id.slice(0, 8)}
      </p>

      <section>
        <h3>Flags</h3>
        {profile.flags.map((f) => (
          <div className="flag" key={f.id}>
            <strong>{f.rule_id}</strong>
            <div className="muted">{f.rule_description}</div>
          </div>
        ))}
      </section>

      <section>
        <h3>Per-domain evidence</h3>
        <p className="muted">
          Domains are independent — there is no composite score. Adjusted score
          applies the school-tier context factor.
        </p>
        <table>
          <thead>
            <tr>
              <th>Domain</th>
              <th>Raw</th>
              <th>Factor</th>
              <th>Adjusted</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {profile.profile.map((d) => (
              <tr key={d.domain}>
                <td>{d.domain}</td>
                <td>{d.raw_score}</td>
                <td>{d.adjustment_factor.toFixed(2)}</td>
                <td>
                  <strong>{d.adjusted_score}</strong>
                </td>
                <td className="evidence">{d.evidence_text}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="context">
        <div>
          <h3>Nomination context</h3>
          <p>
            2e amber-flags: <strong>{profile.nomination_amber_flags}</strong>{" "}
            <span className="muted">(evidence, not a score)</span>
          </p>
        </div>
        <div>
          <h3>Passive candidate signals</h3>
          {profile.candidate_signals.length === 0 && (
            <p className="muted">None.</p>
          )}
          {profile.candidate_signals.map((s) => (
            <div key={s.id} className="signal">
              <span className="pill passive_signal">{s.signal_type}</span>{" "}
              <span className="muted">confidence: {s.confidence} (advisory only)</span>
              <div className="muted">{s.evidence_text}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="decision">
        <h3>Record decision</h3>
        {profile.existing_decision && (
          <p className="muted">
            Latest recorded decision: <strong>{profile.existing_decision}</strong>
          </p>
        )}
        <textarea
          placeholder="Reviewer notes…"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
        <div className="buttons">
          <button disabled={busy} className="advance" onClick={() => decide("advance")}>
            Advance
          </button>
          <button disabled={busy} className="hold" onClick={() => decide("hold")}>
            Hold
          </button>
          <button disabled={busy} className="decline" onClick={() => decide("decline")}>
            Decline
          </button>
        </div>
        {msg && <p className="msg">{msg}</p>}
      </section>
    </div>
  );
}
