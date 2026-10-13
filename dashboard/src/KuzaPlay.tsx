/**
 * Kuza Play — the child-facing way to answer Kuza's puzzles.
 *
 * Built for children who don't like tests:
 *  - It never says "test", never shows a score, never says right/wrong.
 *  - The child picks HOW to play (look & tap, listen, talk, draw) and WHICH
 *    "island" to visit, and can always skip ("try another") or ask for a hint.
 *  - Every question has a picture or is read aloud; answers can be tapped,
 *    put in order, typed, spoken, or drawn.
 *  - Progress is a plant that grows ("kuza" means "grow"), not a percentage.
 *
 * Two modes:
 *  - Explore (default): free play over the whole bank. Nothing is sent to the
 *    server; the grown-up can save the answers as a file at the end.
 *  - Session (#/play?session=<id>): a real, consented screening session that a
 *    staff member started. Follows the server's order of core items and sends
 *    every answer, hint and skip to the gateway, where it is scored as usual.
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  ArrowLeft, Check, Eye, Ear, Hand, Lightbulb, Mic, MicOff, Pencil, RotateCcw,
  SkipForward, Volume2, X, Eraser, Download, Sprout,
} from "lucide-react";
import { Bank, BankItem, Bi, getBank, itemAsset } from "./api";
import "./play.css";

type Lang = "en" | "sw";
type Style = "look" | "listen" | "talk" | "draw";
type Answer = { itemId: string; value: string; hints: number; skipped: boolean; ms: number; mode: string };

const BASE = (import.meta.env.VITE_API_BASE as string) || "/api";

const t = (b: Bi | undefined, l: Lang) => (b ? b[l] || b.en : "");
const T = (en: string, sw: string): Bi => ({ en, sw });

const ISLANDS: Record<string, { name: Bi; emoji: string; color: string }> = {
  numerical_reasoning: { name: T("Market of Numbers", "Soko la Nambari"), emoji: "🥭", color: "#F59E0B" },
  verbal_reasoning: { name: T("Story Tree", "Mti wa Hadithi"), emoji: "🌳", color: "#16A34A" },
  pattern_recognition: { name: T("Bead Workshop", "Karakana ya Shanga"), emoji: "📿", color: "#DC2626" },
  logical_reasoning: { name: T("Puzzle Bus Stop", "Kituo cha Mafumbo"), emoji: "🚌", color: "#2563EB" },
  working_memory: { name: T("Memory Garden", "Bustani ya Kumbukumbu"), emoji: "🌻", color: "#0F766E" },
  creativity: { name: T("Inventors' Corner", "Kona ya Wabunifu"), emoji: "💡", color: "#9333EA" },
};

const CHEERS: Bi[] = [
  T("Nice thinking!", "Umefikiri vizuri!"), T("Thank you for trying that!", "Asante kwa kujaribu!"),
  T("Kuza loved your idea!", "Kuza amependa wazo lako!"), T("Your plant grew a new leaf!", "Mmea wako umeota jani jipya!"),
  T("Great, on to the next one!", "Vizuri, twende kwa linalofuata!"),
];

const UI = {
  hi: T("Hi, I'm Kuza!", "Habari, mimi ni Kuza!"),
  notATest: T("These are puzzles and stories, not a test. No timer, no marks. Skip anything, ask for hints, answer any way you like.",
    "Haya ni mafumbo na hadithi, si mtihani. Hakuna saa, hakuna alama. Ruka lolote, omba dokezo, jibu unavyopenda."),
  how: T("How do you like to play?", "Unapenda kucheza vipi?"),
  look: T("Look & tap", "Tazama & gusa"), listen: T("Listen", "Sikiliza"), talk: T("Talk", "Ongea"), draw: T("Draw & write", "Chora & andika"),
  start: T("Let's go", "Twende"), pick: T("Where shall we go?", "Twende wapi?"),
  quick: T("Kuza's quick trip (5 puzzles)", "Safari fupi ya Kuza (mafumbo 5)"),
  hint: T("Hint", "Dokezo"), skip: T("Try another", "Jaribu jingine"), read: T("Read to me", "Nisomee"),
  done: T("Done", "Nimemaliza"), typeHere: T("Type here, or tap the microphone and talk", "Andika hapa, au gusa kipaza sauti uongee"),
  lookNow: T("Look carefully...", "Tazama kwa makini..."), ready: T("I'm ready", "Niko tayari"),
  playAudio: T("Play the question", "Cheza swali"), heard: T("Listen once, then answer.", "Sikiliza mara moja, kisha jibu."),
  tapOrder: T("Tap the pictures in order", "Gusa picha kwa mpangilio"), undo: T("Undo", "Rudisha"),
  moreHints: T("No more hints for this one. Have a go, or try another!", "Hakuna dokezo zaidi. Jaribu, au chagua jingine!"),
  finish: T("Finish", "Maliza"), feel: T("How did that feel?", "Ulijisikiaje?"),
  thanks: T("Thank you for playing with Kuza!", "Asante kwa kucheza na Kuza!"),
  again: T("Play again", "Cheza tena"), back: T("Islands", "Visiwa"),
  pathInfo: T("You can stop any time. Your answers help grown-ups see how you think.", "Unaweza kusimama wakati wowote. Majibu yako yanasaidia watu wazima kuona unavyofikiri."),
  sessionNote: T("This is a real session: your answers are saved for the Kuza team.", "Hiki ni kipindi halisi: majibu yako yanahifadhiwa kwa timu ya Kuza."),
  clear: T("Clear", "Futa"), nameIt: T("Give your picture a name", "Ipe picha yako jina"),
  interests: T("First, what do you LOVE doing?", "Kwanza, unapenda SANA kufanya nini?"),
};

/* ------------------------------------------------------------- speech helpers */
function speak(text: string, lang: Lang) {
  try {
    const synth = window.speechSynthesis;
    if (!synth) return false;
    synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    const want = lang === "sw" ? "sw" : "en";
    const v = synth.getVoices().find((x) => x.lang.toLowerCase().startsWith(want));
    if (v) u.voice = v;
    u.lang = lang === "sw" ? "sw-KE" : "en-KE";
    u.rate = 0.9;
    synth.speak(u);
    return true;
  } catch { return false; }
}

function useListen(lang: Lang, onText: (t: string) => void) {
  const [on, setOn] = useState(false);
  const rec = useRef<any>(null);
  const Ctor = typeof window !== "undefined" ? ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition) : null;
  function toggle() {
    if (!Ctor) return;
    if (on) { rec.current?.stop(); return; }
    const r = new Ctor();
    r.lang = lang === "sw" ? "sw-KE" : "en-KE";
    r.interimResults = false;
    r.onresult = (e: any) => onText(Array.from(e.results).map((x: any) => x[0].transcript).join(" "));
    r.onend = () => setOn(false);
    r.onerror = () => setOn(false);
    rec.current = r; r.start(); setOn(true);
  }
  return { supported: !!Ctor, on, toggle };
}

/* ------------------------------------------------------------- the component */
export function KuzaPlay({ onExit, standalone = false }: { onExit?: () => void; standalone?: boolean }) {
  const sessionId = useMemo(() => new URLSearchParams(window.location.hash.split("?")[1] || "").get("session"), []);
  const [bank, setBank] = useState<Bank | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [lang, setLang] = useState<Lang>("en");
  const [style, setStyle] = useState<Style>("look");
  const [stage, setStage] = useState<"welcome" | "interests" | "map" | "play" | "end">("welcome");
  const [queue, setQueue] = useState<BankItem[]>([]);
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<Answer[]>([]);
  const [interests, setInterests] = useState<number[]>([]);
  const [cheer, setCheer] = useState<string | null>(null);
  const [mood, setMood] = useState<string | null>(null);
  const [visited, setVisited] = useState<Set<string>>(new Set());
  const [sessionDone, setSessionDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const lastAnswer = useRef<Omit<Answer, "itemId"> | null>(null);
  const langSynced = useRef(false);

  // Fetch the session's language as soon as a session link opens, so even the
  // welcome screen is in the language staff chose.
  useEffect(() => {
    if (!sessionId) return;
    fetch(`${BASE}/screening/sessions/${sessionId}`).then((r) => (r.ok ? r.json() : null)).then((j) => {
      if (j && !langSynced.current && (j.language === "sw" || j.language === "en")) { setLang(j.language); langSynced.current = true; }
    }).catch(() => {});
  }, [sessionId]);

  /** Hints in a recorded session are saved before the child can answer, so
   * the stored answer always knows how many hints were seen. */
  async function sessionHint(itemId: string): Promise<boolean> {
    setBusy(true);
    const res = await sendToSession("hint", itemId);
    setBusy(false);
    if (res === "stale") { await syncSession(); return false; }
    if (!res) { setSaveErr(lang === "sw" ? "Dokezo halikuhifadhiwa. Jaribu tena." : "That hint didn't save. Please try again."); return false; }
    return true;
  }

  useEffect(() => { getBank().then(setBank).catch((e) => setErr(String(e))); }, []);

  const byId = useMemo(() => Object.fromEntries((bank?.items || []).map((i) => [i.id, i])), [bank]);
  const interestItem = bank?.items.find((i) => i.tier === "warmup_unscored");
  const autoRead = style === "listen";

  // ---- session mode: the server decides which core item is next
  async function syncSession() {
    if (!sessionId) return;
    const r = await fetch(`${BASE}/screening/sessions/${sessionId}`);
    if (!r.ok) { setErr("This session link isn't valid any more. Ask your teacher for a new one."); return; }
    const j = await r.json();
    if (j.channel && j.channel !== "web") {
      setErr("This session was started for WhatsApp, SMS or USSD, so it has to be answered on the phone. Ask your teacher for a Kuza Play link."); return;
    }
    // Use the language staff chose for this session (the child can still switch).
    if (!langSynced.current && (j.language === "sw" || j.language === "en")) { setLang(j.language); langSynced.current = true; }
    if (j.status !== "in_progress" || !j.item_id) { setSessionDone(true); setStage("end"); return; }
    const it = byId[j.item_id];
    if (it) { setQueue([it]); setIdx(0); }
  }
  /** Returns the new session state, "stale" if the server is on a different
   * item (e.g. a duplicate submit), or null on a network/server error. */
  async function sendToSession(text: string, itemId: string, ms?: number): Promise<any | "stale" | null> {
    if (!sessionId) return null;
    try {
      const r = await fetch(`${BASE}/screening/responses`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, raw_response: text, response_time_ms: ms, item_id: itemId }),
      });
      if (r.status === 409) return "stale";
      return r.ok ? r.json() : null;
    } catch { return null; }
  }

  function startIsland(domain: string) {
    const items = (bank?.items || []).filter((i) => i.domain === domain).sort((a, b) => a.difficulty - b.difficulty);
    setQueue(items); setIdx(0); setStage("play");
    setVisited((v) => new Set(v).add(domain));
  }
  function startQuick() {
    const core = (bank?.items || []).filter((i) => i.tier === "core").sort((a, b) => a.difficulty - b.difficulty);
    setQueue(core); setIdx(0); setStage("play");
  }
  async function begin() {
    if (sessionId) { await syncSession(); setStage("play"); return; }
    setStage(interestItem ? "interests" : "map");
  }

  function celebrate(a: Omit<Answer, "itemId">, itemId: string) {
    setAnswers((xs) => [...xs, { ...a, itemId }]);
    if (!a.skipped) {
      const c = CHEERS[(answers.length + 1) % CHEERS.length];
      setCheer(t(c, lang)); if (autoRead) speak(t(c, lang), lang);
      window.setTimeout(() => setCheer(null), 1400);
    }
  }

  async function record(a: Omit<Answer, "itemId">) {
    const item = queue[idx];
    if (sessionId) {
      if (busy) return;  // one submit at a time: a double-tap must not answer the next item
      setBusy(true); setSaveErr(null); lastAnswer.current = a;
      const res = await sendToSession(a.skipped ? "skip" : a.value, item.id, a.ms);
      setBusy(false);
      if (res === "stale") { await syncSession(); return; }  // server already moved on: catch up
      if (!res) {
        setSaveErr(lang === "sw" ? "Jibu halikuhifadhiwa. Angalia mtandao kisha ujaribu tena." : "That answer didn't save. Check the connection and try again.");
        return;
      }
      celebrate(a, item.id);
      lastAnswer.current = null;
      if (res.status !== "in_progress" || !res.item_id) { setSessionDone(true); setStage("end"); return; }
      const nxt = byId[res.item_id]; if (nxt) { setQueue([nxt]); setIdx(0); }
      return;
    }
    celebrate(a, item.id);
    if (idx + 1 < queue.length) setIdx(idx + 1);
    else setStage("map");
  }

  function exportAnswers() {
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), language: lang, play_style: style,
      interests: interests.map((i) => interestItem?.choices?.[i]?.en), mood, answers }, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `kuza-play-${Date.now()}.json`; a.click();
  }

  if (err) return <div className={"kp " + (standalone ? "kp-full" : "")}><div className="kp-card"><p>{err}</p></div></div>;
  if (!bank) return <div className={"kp " + (standalone ? "kp-full" : "")}><div className="kp-card"><p>…</p></div></div>;

  const grown = answers.filter((a) => !a.skipped).length;

  return (
    <div className={"kp " + (standalone ? "kp-full" : "")} lang={lang}>
      <header className="kp-top">
        {onExit && <button className="kp-icon" onClick={onExit} aria-label="Exit Kuza Play"><X size={20} /></button>}
        <Plant leaves={grown} />
        <div className="kp-lang" role="group" aria-label="Language">
          <button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>English</button>
          <button className={lang === "sw" ? "on" : ""} onClick={() => setLang("sw")}>Kiswahili</button>
        </div>
      </header>

      {cheer && <div className="kp-cheer" role="status">{cheer}</div>}
      {saveErr && (
        <div className="kp-card kp-error" role="alert">
          <p>{saveErr}</p>
          <button className="kp-go" disabled={busy} onClick={() => lastAnswer.current && record(lastAnswer.current)}><RotateCcw size={18} /> {lang === "sw" ? "Jaribu tena" : "Try again"}</button>
        </div>
      )}

      {stage === "welcome" && (
        <div className="kp-card kp-center">
          <img src="/mascot.png" alt="" className="kp-mascot bob" />
          <h1>{t(UI.hi, lang)}</h1>
          <p className="kp-big">{t(UI.notATest, lang)}</p>
          {sessionId && <p className="kp-note">{t(UI.sessionNote, lang)}</p>}
          <h2>{t(UI.how, lang)}</h2>
          <div className="kp-styles">
            {([["look", <Eye key="i" />], ["listen", <Ear key="i" />], ["talk", <Mic key="i" />], ["draw", <Pencil key="i" />]] as [Style, ReactNode][]).map(([s, icon]) => (
              <button key={s} className={"kp-style " + (style === s ? "on" : "")} onClick={() => { setStyle(s); if (s === "listen") speak(t(UI.notATest, lang), lang); }}
                aria-pressed={style === s}>{icon}<span>{t(UI[s], lang)}</span></button>
            ))}
          </div>
          <button className="kp-go" onClick={begin}>{t(UI.start, lang)} →</button>
        </div>
      )}

      {stage === "interests" && interestItem && (
        <div className="kp-card">
          <h2>{t(UI.interests, lang)} <ReadBtn text={t(interestItem.prompt, lang)} lang={lang} auto={autoRead} /></h2>
          <div className="kp-tiles">
            {interestItem.choices?.map((c, i) => (
              <button key={i} className={"kp-tile " + (interests.includes(i) ? "on" : "")} aria-pressed={interests.includes(i)}
                onClick={() => setInterests((xs) => xs.includes(i) ? xs.filter((x) => x !== i) : [...xs, i])}>
                <span className="kp-letter">{"ABCDEFGH"[i]}</span>{t(c, lang)}
              </button>
            ))}
          </div>
          {interestItem.image && <img className="kp-img small" src={itemAsset(interestItem.image)} alt="" />}
          <button className="kp-go" onClick={() => setStage("map")}>{t(UI.start, lang)} →</button>
        </div>
      )}

      {stage === "map" && (
        <div className="kp-card">
          <h2>{t(UI.pick, lang)}</h2>
          <p className="kp-note">{t(UI.pathInfo, lang)}</p>
          <button className="kp-quick" onClick={startQuick}><Sprout size={20} /> {t(UI.quick, lang)}</button>
          <div className="kp-islands">
            {Object.entries(ISLANDS).map(([d, isl]) => {
              const n = bank.items.filter((i) => i.domain === d).length;
              if (!n) return null;
              return (
                <button key={d} className={"kp-island " + (visited.has(d) ? "visited" : "")} style={{ ["--isl" as any]: isl.color }} onClick={() => startIsland(d)}>
                  <span className="kp-emoji" aria-hidden>{isl.emoji}</span>
                  <b>{t(isl.name, lang)}</b>
                  <span className="kp-count">{n} {lang === "sw" ? "mafumbo" : "puzzles"}{visited.has(d) ? " ✓" : ""}</span>
                </button>
              );
            })}
          </div>
          {answers.length > 0 && <button className="kp-go ghost" onClick={() => setStage("end")}>{t(UI.finish, lang)}</button>}
        </div>
      )}

      {stage === "play" && queue[idx] && (
        <Puzzle key={queue[idx].id + idx} item={queue[idx]} lang={lang} style={style} autoRead={autoRead}
          position={sessionId ? undefined : `${idx + 1} / ${queue.length}`}
          onBack={sessionId ? undefined : () => setStage("map")}
          onHint={sessionId ? () => sessionHint(queue[idx].id) : undefined}
          busy={busy}
          onAnswer={record} />
      )}

      {stage === "end" && (
        <div className="kp-card kp-center">
          <img src="/mascot.png" alt="" className="kp-mascot bob" />
          <h1>{t(UI.thanks, lang)}</h1>
          <Plant leaves={grown} big />
          <h2>{t(UI.feel, lang)}</h2>
          <div className="kp-moods">
            {["😄", "🙂", "😐", "😕", "😴"].map((m) => (
              <button key={m} className={mood === m ? "on" : ""} onClick={() => setMood(m)} aria-label={m}>{m}</button>
            ))}
          </div>
          {!sessionId && (
            <div className="kp-row">
              <button className="kp-go" onClick={() => { setAnswers([]); setVisited(new Set()); setStage("map"); }}><RotateCcw size={18} /> {t(UI.again, lang)}</button>
              <button className="kp-go ghost" onClick={exportAnswers}><Download size={18} /> {lang === "sw" ? "Hifadhi majibu (mtu mzima)" : "Save answers (grown-up)"}</button>
            </div>
          )}
          {!sessionId && <p className="kp-note">{lang === "sw"
            ? "Hali ya kucheza: majibu hayatumwi popote. Kwa uchunguzi halisi, mwalimu anaanzisha kipindi na kukupa kiungo."
            : "Explore mode: answers are not sent anywhere. For a real screening, a teacher starts a session and gives you a link."}</p>}
          {sessionDone && sessionId && <p className="kp-note">{lang === "sw" ? "Majibu yako yamehifadhiwa." : "Your answers are saved."}</p>}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- one puzzle */
function Puzzle({ item, lang, style, autoRead, position, onBack, onHint, onAnswer, busy = false }: {
  item: BankItem; lang: Lang; style: Style; autoRead: boolean; position?: string; busy?: boolean;
  onBack?: () => void; onHint?: () => Promise<boolean>; onAnswer: (a: Omit<Answer, "itemId">) => void;
}) {
  const started = useRef(Date.now());
  const [hintsShown, setHintsShown] = useState(0);
  const [noMoreHints, setNoMoreHints] = useState(false);
  const isMemory = !!item.show_seconds;
  const [phase, setPhase] = useState<"show" | "ask">(isMemory ? "show" : "ask");
  const [secs, setSecs] = useState(item.show_seconds || 0);
  const [audioPlays, setAudioPlays] = useState(0);
  const modes = item.response_modes || ["tap", "type", "voice"];
  const canDraw = modes.includes("draw") || modes.includes("photo");
  const hasChoices = !!item.choices?.length && ["choice", "multi_choice", "order"].includes(item.type);
  const [inputMode, setInputMode] = useState<"tap" | "type" | "draw">(
    hasChoices ? "tap" : canDraw && (style === "draw" || item.type === "draw") ? "draw" : "type");
  const [picked, setPicked] = useState<number[]>([]);
  const [text, setText] = useState("");
  const [drawing, setDrawing] = useState<string | null>(null);
  const isGridPath = item.id === "wmm-p3";
  const [path, setPath] = useState<string[]>([]);

  // Memory puzzles: while the picture shows we say "look carefully" (and in
  // listen mode speak the things to remember); once it hides we ask
  // `ask_prompt`, which never repeats what had to be remembered.
  const promptText = isMemory && phase === "ask" && item.ask_prompt ? t(item.ask_prompt, lang) : t(item.prompt, lang);
  const showText = item.show_script ? `${t(UI.lookNow, lang)} ${t(item.show_script, lang)}` : t(UI.lookNow, lang);
  useEffect(() => {
    if (!autoRead || item.audio_only) return;
    speak(phase === "show" ? `${t(item.prompt, lang)} ${item.show_script ? t(item.show_script, lang) : ""}` : promptText, lang);
    /* eslint-disable-next-line */
  }, [item.id, lang, phase]);

  useEffect(() => {
    if (phase !== "show") return;
    if (secs <= 0) { setPhase("ask"); return; }
    const h = window.setTimeout(() => setSecs((s) => s - 1), 1000);
    return () => window.clearTimeout(h);
  }, [phase, secs]);

  const mic = useListen(lang, (said) => setText((x) => (x ? x + " " : "") + said));

  async function hint() {
    if (hintsShown >= (item.hints?.length || 0)) { setNoMoreHints(true); return; }
    // In a recorded session, show the hint only once the server has saved it.
    if (onHint && !(await onHint())) return;
    const h = t(item.hints![hintsShown], lang);
    setHintsShown(hintsShown + 1);
    if (autoRead) speak(h, lang);
  }

  function value(): string {
    const parts: string[] = [];
    if (isGridPath && path.length) parts.push(path.join(", "));
    if (picked.length) parts.push(picked.map((i) => "ABCDEFGH"[i]).join(" "));
    if (text.trim()) parts.push(text.trim());
    if (drawing) parts.push("[drawing made on screen]");
    return parts.join(" | ");
  }
  const ready = !!value();

  function submit(skipped = false) {
    window.speechSynthesis?.cancel();
    onAnswer({ value: skipped ? "" : value(), hints: hintsShown, skipped, ms: Date.now() - started.current,
      mode: [picked.length && "tap", text && (mic.on ? "voice" : "type"), drawing && "draw", path.length && "path"].filter(Boolean).join("+") || "none" });
  }

  const isl = ISLANDS[item.domain];
  const img = phase === "show" ? item.image : (item.image_after || (isMemory ? undefined : item.image));

  return (
    <div className="kp-card kp-puzzle" style={{ ["--isl" as any]: isl?.color || "#0F766E" }}>
      <div className="kp-puzzletop">
        {onBack && <button className="kp-icon" onClick={onBack} aria-label={t(UI.back, lang)}><ArrowLeft size={20} /></button>}
        <span className="kp-islandtag">{isl?.emoji} {isl ? t(isl.name, lang) : item.domain}</span>
        {position && <span className="kp-pos">{position}</span>}
      </div>

      {item.audio_only ? (
        <div className="kp-audio">
          <p className="kp-big">{t(UI.heard, lang)}</p>
          <button className="kp-go" onClick={() => { speak(promptText, lang); setAudioPlays((n) => n + 1); }}>
            <Volume2 size={22} /> {t(UI.playAudio, lang)}
          </button>
          {audioPlays > 1 && <p className="kp-note">{lang === "sw" ? `Umesikiliza mara ${audioPlays}` : `Played ${audioPlays} times`}</p>}
        </div>
      ) : (
        <p className="kp-prompt">{phase === "show" ? t(item.prompt, lang) : promptText}
          <ReadBtn text={phase === "show" ? showText : promptText} lang={lang} /></p>
      )}

      {img && !(inputMode === "draw" && item.type === "draw") && <img className="kp-img" src={itemAsset(img)} alt={phase === "show" ? t(UI.lookNow, lang) : promptText} />}
      {phase === "show" && (
        <div className="kp-row">
          <div className="kp-timer" aria-label={`${secs}`}><span style={{ width: `${(secs / (item.show_seconds || 1)) * 100}%` }} /></div>
          <button className="kp-go ghost" onClick={() => setPhase("ask")}>{t(UI.ready, lang)}</button>
        </div>
      )}

      {phase === "ask" && (
        <>
          {hintsShown > 0 && (
            <div className="kp-hints">{item.hints!.slice(0, hintsShown).map((h, i) => <p key={i}><Lightbulb size={16} /> {t(h, lang)}</p>)}</div>
          )}
          {noMoreHints && <p className="kp-note">{t(UI.moreHints, lang)}</p>}

          <div className="kp-modes" role="group" aria-label="Answer with">
            {hasChoices && <button className={inputMode === "tap" ? "on" : ""} onClick={() => setInputMode("tap")}><Hand size={16} /> {t(UI.look, lang)}</button>}
            {(modes.includes("type") || modes.includes("voice")) && <button className={inputMode === "type" ? "on" : ""} onClick={() => setInputMode("type")}><Mic size={16} /> {t(UI.talk, lang)} / {lang === "sw" ? "andika" : "type"}</button>}
            {canDraw && <button className={inputMode === "draw" ? "on" : ""} onClick={() => setInputMode("draw")}><Pencil size={16} /> {t(UI.draw, lang)}</button>}
          </div>

          {isGridPath && <PathPad value={path} onChange={setPath} lang={lang} />}

          {inputMode === "tap" && hasChoices && (
            item.type === "order"
              ? <OrderPad item={item} lang={lang} value={picked} onChange={setPicked} />
              : <div className="kp-tiles">
                  {item.choices!.map((c, i) => {
                    const on = picked.includes(i);
                    return (
                      <button key={i} className={"kp-tile " + (on ? "on" : "")} aria-pressed={on}
                        onClick={() => setPicked(item.type === "multi_choice" ? (on ? picked.filter((x) => x !== i) : [...picked, i]) : [i])}>
                        <span className="kp-letter">{"ABCDEFGH"[i]}</span>{t(c, lang)}
                      </button>
                    );
                  })}
                </div>
          )}

          {inputMode === "type" && (
            <div className="kp-textwrap">
              <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={t(UI.typeHere, lang)} rows={3} />
              {mic.supported && (
                <button className={"kp-mic " + (mic.on ? "on" : "")} onClick={mic.toggle} aria-label={mic.on ? "Stop listening" : "Talk"}>
                  {mic.on ? <MicOff size={26} /> : <Mic size={26} />}
                </button>
              )}
            </div>
          )}
          {inputMode === "tap" && hasChoices && (modes.includes("voice") || modes.includes("type")) && item.type !== "multi_choice" && (
            <input className="kp-why" value={text} onChange={(e) => setText(e.target.value)}
              placeholder={lang === "sw" ? "Kwa nini? (si lazima)" : "Why? (only if you want to)"} />
          )}

          {inputMode === "draw" && (
            <>
              <DrawPad bg={item.type === "draw" && item.image ? itemAsset(item.image) : undefined} onChange={setDrawing} lang={lang} />
              <input className="kp-why" value={text} onChange={(e) => setText(e.target.value)} placeholder={t(UI.nameIt, lang)} />
            </>
          )}

          <div className="kp-actions">
            {(item.hints?.length || 0) > 0 && <button className="kp-soft" disabled={busy} onClick={hint}><Lightbulb size={18} /> {t(UI.hint, lang)}</button>}
            <button className="kp-soft" disabled={busy} onClick={() => submit(true)}><SkipForward size={18} /> {t(UI.skip, lang)}</button>
            <button className="kp-go" disabled={!ready || busy} onClick={() => submit(false)}><Check size={20} /> {t(UI.done, lang)}</button>
          </div>
        </>
      )}
    </div>
  );
}

function ReadBtn({ text, lang, auto }: { text: string; lang: Lang; auto?: boolean }) {
  useEffect(() => { if (auto) speak(text, lang); /* eslint-disable-next-line */ }, []);
  if (typeof window === "undefined" || !window.speechSynthesis) return null;
  return <button className="kp-read" onClick={() => speak(text, lang)} aria-label={t(UI.read, lang)} title={t(UI.read, lang)}><Volume2 size={18} /></button>;
}

function OrderPad({ item, lang, value, onChange }: { item: BankItem; lang: Lang; value: number[]; onChange: (v: number[]) => void }) {
  return (
    <div>
      <p className="kp-note">{t(UI.tapOrder, lang)}</p>
      <div className="kp-tiles">
        {item.choices!.map((c, i) => {
          const pos = value.indexOf(i);
          return (
            <button key={i} className={"kp-tile " + (pos >= 0 ? "on" : "")} disabled={pos >= 0}
              onClick={() => onChange([...value, i])}>
              <span className="kp-letter">{pos >= 0 ? pos + 1 : "ABCDEFGH"[i]}</span>{t(c, lang)}
            </button>
          );
        })}
      </div>
      <div className="kp-orderline">
        {value.map((i, n) => <span key={n} className="kp-chip">{n + 1}. {t(item.choices![i], lang)}</span>)}
        {value.length > 0 && <button className="kp-soft" onClick={() => onChange(value.slice(0, -1))}><RotateCcw size={16} /> {t(UI.undo, lang)}</button>}
      </div>
    </div>
  );
}

function PathPad({ value, onChange, lang }: { value: string[]; onChange: (v: string[]) => void; lang: Lang }) {
  const dirs: [string, string, Bi][] = [["up", "↑", T("up", "juu")], ["left", "←", T("left", "kushoto")], ["right", "→", T("right", "kulia")], ["down", "↓", T("down", "chini")]];
  return (
    <div className="kp-path">
      <div className="kp-arrows">
        {dirs.map(([k, arrow, label]) => <button key={k} onClick={() => onChange([...value, k])} aria-label={t(label, lang)}>{arrow}</button>)}
      </div>
      <div className="kp-orderline">
        {value.map((d, i) => <span key={i} className="kp-chip">{dirs.find((x) => x[0] === d)?.[1]}</span>)}
        {value.length > 0 && <button className="kp-soft" onClick={() => onChange(value.slice(0, -1))}><RotateCcw size={16} /> {t(UI.undo, lang)}</button>}
      </div>
    </div>
  );
}

function DrawPad({ bg, onChange, lang }: { bg?: string; onChange: (d: string | null) => void; lang: Lang }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const drawingRef = useRef(false);
  const [color, setColor] = useState("#0B3B3A");
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d")!; ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, c.width, c.height);
    if (bg) { const im = new Image(); im.onload = () => ctx.drawImage(im, 0, 0, c.width, c.height); im.src = bg; }
  }, [bg]);
  function pos(e: React.PointerEvent) {
    const r = ref.current!.getBoundingClientRect();
    return [(e.clientX - r.left) * (ref.current!.width / r.width), (e.clientY - r.top) * (ref.current!.height / r.height)];
  }
  return (
    <div className="kp-draw">
      <canvas ref={ref} width={640} height={400}
        onPointerDown={(e) => { drawingRef.current = true; (e.target as HTMLElement).setPointerCapture(e.pointerId);
          const ctx = ref.current!.getContext("2d")!; const [x, y] = pos(e); ctx.beginPath(); ctx.moveTo(x, y); }}
        onPointerMove={(e) => { if (!drawingRef.current) return; const ctx = ref.current!.getContext("2d")!; const [x, y] = pos(e);
          ctx.strokeStyle = color; ctx.lineWidth = color === "#ffffff" ? 22 : 6; ctx.lineCap = "round"; ctx.lineTo(x, y); ctx.stroke(); }}
        onPointerUp={() => { drawingRef.current = false; onChange(ref.current!.toDataURL("image/png")); }} />
      <div className="kp-palette">
        {["#0B3B3A", "#DC2626", "#2563EB", "#16A34A", "#F59E0B", "#9333EA"].map((c) => (
          <button key={c} style={{ background: c }} className={color === c ? "on" : ""} onClick={() => setColor(c)} aria-label={`colour ${c}`} />
        ))}
        <button className={"kp-soft " + (color === "#ffffff" ? "on" : "")} onClick={() => setColor("#ffffff")}><Eraser size={16} /></button>
        <button className="kp-soft" onClick={() => { const c = ref.current!; const ctx = c.getContext("2d")!; ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, c.width, c.height);
          if (bg) { const im = new Image(); im.onload = () => ctx.drawImage(im, 0, 0, c.width, c.height); im.src = bg; } onChange(null); }}>{t(UI.clear, lang)}</button>
      </div>
    </div>
  );
}

function Plant({ leaves, big = false }: { leaves: number; big?: boolean }) {
  const n = Math.min(leaves, 12);
  const h = 18 + n * 7;
  return (
    <svg className={"kp-plant " + (big ? "big" : "")} viewBox="0 0 80 120" aria-label={`${leaves} leaves`} role="img">
      <rect x="18" y="98" width="44" height="18" rx="5" fill="#B45309" stroke="#0B3B3A" strokeWidth="3" />
      <path d={`M40 98 L40 ${98 - h}`} stroke="#15803D" strokeWidth="4" strokeLinecap="round" />
      {Array.from({ length: n }).map((_, i) => {
        const y = 92 - i * 7; const left = i % 2 === 0;
        return <path key={i} d={left ? `M40 ${y} C30 ${y - 10} 20 ${y - 6} 16 ${y - 2} C24 ${y + 2} 34 ${y + 2} 40 ${y}` : `M40 ${y} C50 ${y - 10} 60 ${y - 6} 64 ${y - 2} C56 ${y + 2} 46 ${y + 2} 40 ${y}`}
          fill="#22C55E" stroke="#0B3B3A" strokeWidth="2" />;
      })}
      {leaves >= 5 && <circle cx="40" cy={98 - h - 4} r="7" fill="#FBBF24" stroke="#0B3B3A" strokeWidth="2" />}
    </svg>
  );
}
