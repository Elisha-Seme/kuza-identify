/**
 * Staff-side screens: sign-in, Insights (metrics + audit log), Admin (accounts,
 * demo tools), Run a session (school staff), and the Question bank gallery
 * with printable puzzle cards for paper / facilitator delivery.
 */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Lock, LogIn, LogOut, Play, Printer, ShieldCheck, UserPlus, Link2, Copy, Users, ScrollText, BarChart3 } from "lucide-react";
import {
  AdminUserRow, AuditRow, Bank, BankItem, Metrics, StaffRole, StaffUser, SchoolRow,
  bindPhone, createUser, deactivateUser, getAuditLog, getBank, getMetrics, itemAsset, listSchools, listUsers, login,
  runDemoScreening, signOut, startSession,
} from "./api";

export const ROLE_LABELS: Record<StaffRole, string> = {
  reviewer: "Panel reviewer", panel_lead: "Panel lead", programme_admin: "Programme admin",
  auditor: "Auditor (read-only)", school_staff: "School staff",
};

/* ------------------------------------------------------------- sign in */
export function SignIn({ why }: { why: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function go(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try { await login(email, password); } catch (x) { setErr(x instanceof Error ? x.message : String(x)); } finally { setBusy(false); }
  }
  return (
    <div className="formcard signin">
      <div className="safeguard"><Lock size={18} className="lic" /><span>{why}</span></div>
      <form onSubmit={go}>
        <div className="field"><label>Work email<input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></label></div>
        <div className="field"><label>Password<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label></div>
        {err && <div className="error">{err}</div>}
        <button className="primary" disabled={busy} type="submit"><LogIn size={16} className="lic" />{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <p className="muted small">Accounts are created by a programme admin. Parents and teachers don't need one: use <b>Refer a learner</b>.</p>
    </div>
  );
}

export function WhoAmI({ user }: { user: StaffUser }) {
  return (
    <div className="whoami">
      <ShieldCheck size={15} className="lic" />
      <span><b>{user.display_name}</b> · {ROLE_LABELS[user.role]}</span>
      <button onClick={signOut}><LogOut size={14} className="lic" />Sign out</button>
    </div>
  );
}

/** Wraps a staff screen: shows sign-in if needed, or a polite "not your role". */
export function Gate({ user, roles, why, children }: { user: StaffUser | null; roles: StaffRole[]; why: string; children: ReactNode }) {
  if (!user) return <SignIn why={why} />;
  if (!roles.includes(user.role)) {
    return <div className="formcard"><div className="safeguard"><Lock size={18} className="lic" />
      <span>Your role ({ROLE_LABELS[user.role]}) doesn't include this section. Ask a programme admin if you need it.</span></div></div>;
  }
  return <>{children}</>;
}

/* ------------------------------------------------------------- insights */
export function InsightsTab({ user }: { user: StaffUser }) {
  const [m, setM] = useState<Metrics | null>(null);
  const [log, setLog] = useState<AuditRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const canAudit = ["panel_lead", "programme_admin", "auditor"].includes(user.role);
  useEffect(() => {
    getMetrics().then(setM).catch((e) => setErr(String(e)));
    if (canAudit) getAuditLog().then(setLog).catch(() => setLog([]));
  }, [canAudit]);
  const DIM: Record<string, string> = { pathway: "Pathway", school_tier: "School tier", language: "Language", gender: "Gender" };
  return (
    <div>
      <div className="pageheader">
        <h2 className="pagetitle">Insights and fairness</h2>
        <p className="lead">Aggregate counts only. Any count under 5 shows as "&lt;5" so a small group can't point to one child. Compare flag and advance rates across slices: a big gap is something to discuss, not proof of bias on its own.</p>
      </div>
      {err && <div className="error">{err}</div>}
      {m && (
        <div className="formcard">
          <h3><BarChart3 size={16} className="lic" /> Pilot funnel</h3>
          <div className="statrow">
            {Object.entries(m.funnel).map(([k, v]) => (
              <div className="statcard" key={k}><div><div className="n">{String(v)}</div><div className="lbl">{k.replace(/_/g, " ")}</div></div></div>
            ))}
          </div>
          {Object.entries(m.slices).map(([dim, rows]) => (
            <div key={dim} style={{ marginTop: 14 }}>
              <h3>{DIM[dim] ?? dim}</h3>
              <table className="counts">
                <thead><tr><th>Group</th><th>Sessions</th><th>Flagged</th><th>Advanced</th></tr></thead>
                <tbody>{Object.entries(rows).map(([g, r]) => (
                  <tr key={g}><td>{g}</td><td>{String(r.sessions)}</td><td>{String(r.flagged)}</td><td>{String(r.advanced)}</td></tr>
                ))}</tbody>
              </table>
            </div>
          ))}
        </div>
      )}
      {canAudit && (
        <div className="formcard" style={{ marginTop: 14 }}>
          <h3><ScrollText size={16} className="lic" /> Audit log (append-only)</h3>
          <p className="muted small">Every flag and every decision, newest first. Nobody can edit or delete these rows; the database refuses.</p>
          {log === null ? <div className="loading">Loading.</div> : log.length === 0 ? <p className="muted small">No entries yet.</p> : (
            <table className="counts">
              <thead><tr><th>When</th><th>Event</th><th>Session</th><th>Detail</th></tr></thead>
              <tbody>{log.slice(0, 100).map((r) => (
                <tr key={r.id}><td>{new Date(r.logged_at).toLocaleString()}</td><td>{r.event_type}</td>
                  <td><code>{r.session_id.slice(0, 8)}</code></td>
                  <td className="small">{String((r.detail as any).rule_id ?? (r.detail as any).decision ?? "")}</td></tr>
              ))}</tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- admin */
export function AdminTab({ user }: { user: StaffUser }) {
  const [users, setUsers] = useState<AdminUserRow[] | null>(null);
  const [schools, setSchools] = useState<SchoolRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [form, setForm] = useState({ email: "", display_name: "", role: "reviewer" as StaffRole, password: "", school_id: "" });
  const refresh = () => listUsers().then(setUsers).catch((e) => setErr(String(e)));
  useEffect(() => { refresh(); listSchools().then(setSchools).catch(() => {}); }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null);
    try {
      await createUser({ ...form, school_id: form.role === "school_staff" ? form.school_id || null : null });
      setMsg(`Account created for ${form.email}. Share the password with them privately; ask them to keep it safe.`);
      setForm({ email: "", display_name: "", role: "reviewer", password: "", school_id: "" }); refresh();
    } catch (x) { setErr(x instanceof Error ? x.message : String(x)); }
  }
  async function demo() {
    setMsg("Running a demo screening through the scorer…");
    try { const r = await runDemoScreening(); setMsg(`Demo profile created (scored by ${r.scored_by}). Open Panel review to see it.`); }
    catch (x) { setErr(x instanceof Error ? x.message : String(x)); }
  }
  return (
    <div>
      <div className="pageheader">
        <h2 className="pagetitle">Admin</h2>
        <p className="lead">Staff accounts and roles. Each role sees only what it needs: reviewers see learner profiles, auditors see aggregates and the audit log, school staff can only start sessions for learners at their own school.</p>
      </div>
      {err && <div className="error">{err}</div>}
      {msg && <div className="banner info"><span>{msg}</span></div>}
      <div className="formsplit">
        <form className="formcard" onSubmit={add}>
          <h3><UserPlus size={16} className="lic" /> New staff account</h3>
          <div className="field"><label>Name<input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} required /></label></div>
          <div className="field"><label>Work email<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></label></div>
          <div className="field"><label>Role
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as StaffRole })}>
              {(Object.keys(ROLE_LABELS) as StaffRole[]).map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </select></label></div>
          {form.role === "school_staff" && (
            <div className="field"><label>School
              <select value={form.school_id} onChange={(e) => setForm({ ...form, school_id: e.target.value })} required>
                <option value="">Choose…</option>{schools.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select></label></div>
          )}
          <div className="field"><label>Temporary password (10+ characters)<input type="text" minLength={10} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required /></label></div>
          <button className="primary" type="submit">Create account</button>
        </form>
        <div className="formcard">
          <h3><Users size={16} className="lic" /> Accounts</h3>
          {users === null ? <div className="loading">Loading.</div> : (
            <table className="counts">
              <thead><tr><th>Name</th><th>Role</th><th>Status</th><th></th></tr></thead>
              <tbody>{users.map((u) => (
                <tr key={u.id}><td>{u.display_name}<div className="muted small" style={{ textTransform: "none" }}>{u.email}</div></td><td>{ROLE_LABELS[u.role]}</td>
                  <td>{u.active ? "Active" : "Deactivated"}</td>
                  <td>{u.active && u.id !== user.id && <button onClick={() => deactivateUser(u.id).then(refresh).catch((e) => setErr(String(e)))}>Deactivate</button>}</td></tr>
              ))}</tbody>
            </table>
          )}
          <h3 style={{ marginTop: 18 }}>Demo tools</h3>
          <p className="muted small">Creates a consented demo learner and runs the five core puzzles through the scorer (costs real LLM calls when live scoring is on).</p>
          <button onClick={demo}><Play size={15} className="lic" />Run demo screening</button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- run a session */
export function RunSessionTab() {
  const [learner, setLearner] = useState("");
  const [lang, setLang] = useState<"en" | "sw">("en");
  const [channel, setChannel] = useState<"web" | "whatsapp" | "sms" | "ussd">("web");
  const [phone, setPhone] = useState("");
  const [link, setLink] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function go(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null); setLink(null);
    try {
      const s = await startSession(learner.trim(), channel, lang);
      if (channel === "web") setLink(`${window.location.origin}/#/play?session=${s.session_id}`);
      else { await bindPhone(channel, phone, s.session_id); setMsg(channel === "ussd"
        ? "Session started. The learner dials the Kuza USSD code from that phone to begin."
        : `Session started. The first question has been sent to that phone by ${channel === "sms" ? "SMS" : "WhatsApp"}; the learner just replies.`); }
    } catch (x) { setErr(x instanceof Error ? x.message : String(x)); }
  }
  return (
    <div>
      <div className="pageheader">
        <h2 className="pagetitle">Run a screening session</h2>
        <p className="lead">For a learner whose guardian has given screening consent. Choose how the child will take part: <b>Kuza Play</b> on a tablet or phone browser (pictures, read-aloud, tap, talk or draw), or by phone over WhatsApp, SMS or USSD.</p>
      </div>
      <form className="formcard" onSubmit={go}>
        <div className="field"><label>Learner ID (from the referral confirmation)<input value={learner} onChange={(e) => setLearner(e.target.value)} placeholder="e.g. 7a381663-…" required /></label></div>
        <div className="field"><label>How will they take part?
          <select value={channel} onChange={(e) => setChannel(e.target.value as any)}>
            <option value="web">Kuza Play (tablet / browser)</option><option value="whatsapp">WhatsApp (pictures + text)</option>
            <option value="sms">SMS (text only, any phone)</option><option value="ussd">USSD (no airtime needed)</option>
          </select></label></div>
        {channel !== "web" && <div className="field"><label>Phone number<input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+2547…" required /></label></div>}
        <div className="field"><label>Language
          <select value={lang} onChange={(e) => setLang(e.target.value as any)}><option value="en">English</option><option value="sw">Kiswahili</option></select></label></div>
        {err && <div className="error">{err}</div>}
        {msg && <div className="banner info"><span>{msg}</span></div>}
        <button className="primary" type="submit"><Play size={15} className="lic" />Start session</button>
        {link && (
          <div className="banner info" style={{ marginTop: 12 }}><Link2 size={16} className="lic" />
            <span>Open this on the child's device: <a href={link} target="_blank" rel="noreferrer">{link}</a>
              <button type="button" onClick={() => navigator.clipboard?.writeText(link)} style={{ marginLeft: 8 }}><Copy size={14} className="lic" />Copy</button></span>
          </div>
        )}
      </form>
    </div>
  );
}

/* ------------------------------------------------------------- question bank */
const DELIVERY_LABELS: Record<string, string> = {
  web_play: "Kuza Play", whatsapp_image: "WhatsApp picture", whatsapp_voice: "WhatsApp voice note", whatsapp_view_once: "WhatsApp view-once",
  ivr_voice: "Voice call", sms_text: "SMS", ussd_text: "USSD", facilitator_cards: "Printed card", paper_photo: "Paper + photo",
  hands_on_sticks: "Real sticks", hands_on_role_play: "Act it out", hands_on_model: "Build a model",
};
const RESPONSE_LABELS: Record<string, string> = { tap: "Tap", type: "Type", voice: "Talk", draw: "Draw", photo: "Photo", drag: "Put in order", hands_on: "Hands-on" };
const DOMAIN_NAMES: Record<string, string> = {
  numerical_reasoning: "Numeracy", verbal_reasoning: "Verbal", pattern_recognition: "Patterns", logical_reasoning: "Logic",
  working_memory: "Memory", creativity: "Creativity", interests: "Interests (not scored)",
};
const TIER_NAMES: Record<string, string> = { core: "Core session", pool: "Pool", bonus_off_level: "Off-level", bonus_creativity: "Creativity", warmup_unscored: "Warm-up" };

export function QuestionBankTab({ onPlay }: { onPlay: () => void }) {
  const [bank, setBank] = useState<Bank | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [domain, setDomain] = useState("all");
  const [delivery, setDelivery] = useState("all");
  useEffect(() => { getBank().then(setBank).catch((e) => setErr(String(e))); }, []);
  const items = useMemo(() => (bank?.items || []).filter((i) =>
    (domain === "all" || i.domain === domain) && (delivery === "all" || (i.delivery || []).includes(delivery))), [bank, domain, delivery]);
  const counts = useMemo(() => {
    const all = bank?.items || [];
    return { total: all.length, pics: all.filter((i) => i.image).length, voice: all.filter((i) => (i.response_modes || []).includes("voice")).length,
      draw: all.filter((i) => (i.response_modes || []).includes("draw")).length };
  }, [bank]);
  return (
    <div>
      <div className="pageheader noprint">
        <h2 className="pagetitle">Puzzle bank</h2>
        <p className="lead">Every puzzle has a picture or is read aloud, a plain-text version for SMS/USSD, and several ways to answer. Children can tap, talk, put things in order, draw, or do it with real objects. Five are the automatic core session; the rest give more evidence and more choice. Answer keys and scorer notes stay on the server.</p>
        {bank && <div className="qmeta">
          <div className="qmetaitem"><div><b>{counts.total} puzzles</b><span className="muted"> 5 areas + creativity</span></div></div>
          <div className="qmetaitem"><div><b>{counts.pics} with pictures</b><span className="muted"> also work as audio</span></div></div>
          <div className="qmetaitem"><div><b>{counts.voice} by voice, {counts.draw} by drawing</b><span className="muted"> as well as tapping or typing</span></div></div>
        </div>}
        <div className="filters">
          <label>Area<select value={domain} onChange={(e) => setDomain(e.target.value)}>
            <option value="all">All</option>{Object.entries(DOMAIN_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label>Works on<select value={delivery} onChange={(e) => setDelivery(e.target.value)}>
            <option value="all">Any channel</option>{Object.entries(DELIVERY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <div className="controls" style={{ alignSelf: "flex-end" }}>
            <button onClick={onPlay}><Play size={15} className="lic" />Open Kuza Play</button>
            <button onClick={() => window.print()}><Printer size={15} className="lic" />Print puzzle cards</button>
          </div>
        </div>
      </div>
      {err && <div className="error">{err}</div>}
      {!bank ? <div className="loading">Loading puzzles.</div> : (
        <div className="printarea"><div className="printcards">{items.map((i) => <Card key={i.id} it={i} />)}</div></div>
      )}
    </div>
  );
}

function Card({ it }: { it: BankItem }) {
  return (
    <div className="printcard">
      <div className="pc-top"><span><b>{DOMAIN_NAMES[it.domain] ?? it.domain}</b> · level {it.difficulty}</span><span>{TIER_NAMES[it.tier] ?? it.tier} · {it.id}</span></div>
      {it.image && <img src={itemAsset(it.image)} alt={it.text_fallback?.en || it.prompt.en} loading="lazy" />}
      {it.image_after && <img src={itemAsset(it.image_after)} alt="" loading="lazy" style={{ marginTop: 6 }} />}
      {it.audio_only && <p className="muted small">🔊 Read aloud once, no picture.</p>}
      <p className="pc-en">{it.prompt.en}</p>
      <p className="pc-sw">{it.prompt.sw}</p>
      {it.choices && <div className="pc-choices">{it.choices.map((c, n) => <span key={n}>{"ABCDEFGH"[n]}. {c.en} / {c.sw}</span>)}</div>}
      {it.hints && it.hints.length > 0 && <p className="small muted">💡 {it.hints.length} hint{it.hints.length > 1 ? "s" : ""}: {it.hints[0].en}</p>}
      <div className="pc-modes">
        {(it.response_modes || []).map((m) => <span key={m}>{RESPONSE_LABELS[m] ?? m}</span>)}
        {(it.delivery || []).map((d) => <span key={d} style={{ background: "#e6f4f1" }}>{DELIVERY_LABELS[d] ?? d}</span>)}
      </div>
    </div>
  );
}
