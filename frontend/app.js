import { Pitch } from "./pitch.js";
import { Playout } from "./playout.js";
import { Voice } from "./voice.js";
import { initCompare } from "./compare.js";
import { initVision } from "./vision.js";
import { segmentCard, segmentFoot } from "./render.js";
import { LANG_NAMES, applyStatic, setUiLang, t, uiLang } from "./i18n.js";
import { STATIC, getJSON, openStream, postJSON } from "./api.js";

const $ = (id) => document.getElementById(id);
const COLORS = { home: "#c5f665", away: "#ed9e83" };
const AGENTS = [
  ["director", "Director", "plans what airs"],
  ["stats-producer", "Stats producer", "tool calls → facts"],
  ["play-by-play", "Play-by-play", "the call"],
  ["analyst", "Analyst", "context & colour"],
  ["storyline", "Storyline", "remembers the match"],
  ["fact-checker", "Fact-checker", "traces every claim"],
  ["localizer", "Localizer", "your language"],
  ["guide", "Guide", "rules & pitch location"],
  ["recap-editor", "Recap editor", "half & full time"],
];
const AGENT_NAMES = Object.fromEntries(AGENTS.map(([id, name]) => [id, name]));
const KIND_NAMES = { pbp: "Play-by-play", color: "Analyst", stats: "Stats desk", explain: "Guide", spatial: "Guide",
  recap: "Recap editor" };
const BIG = new Set(["goal", "red_card", "penalty_awarded", "half_time", "full_time"]);
const TOAST = { goal: "GOAL", shot: "SHOT", corner: "CORNER", foul: "FOUL", yellow_card: "YELLOW CARD",
  red_card: "RED CARD", penalty_awarded: "PENALTY", offside: "OFFSIDE", substitution: "SUBSTITUTION",
  kickoff: "KICK-OFF", half_time: "HALF TIME", full_time: "FULL TIME", free_kick: "FREE KICK" };
const STAT_ROWS = [["possession_pct", "Possession %"], ["shots", "Shots"], ["shots_on_target", "On target"],
  ["fastest_shot_kmh", "Fastest shot (km/h)"], ["corners", "Corners"], ["passes", "Passes"],
  ["pass_accuracy_pct", "Pass accuracy %"], ["avg_pass_difficulty", "Avg pass difficulty (0-100)"],
  ["distance_km", "Distance (km)"], ["sprints", "Sprints"],
  ["fouls", "Fouls"], ["yellow_cards", "Yellow cards"], ["saves", "Saves"]];
// Thresholds for metric call-outs (the brief's "indicators triggered when predefined thresholds are reached").
const FAST_SHOT_KMH = 100;
const LONG_BALL_M = 45;
const KILLER_PASS = 80;

const voice = new Voice();
const GENDER_KEY = "booth.voiceGender";
try {
  voice.setGender(localStorage.getItem(GENDER_KEY) ?? "female");
} catch {
  // storage blocked: keep the default voice
}
const pitch = new Pitch($("pitch"), COLORS);
let source = null;
let players = {};
let meta = null;
let currentMinute = 0;
let currentPeriod = 1;
let profile = null;
let traceSteps = 0;
let playout = null;
let llm = { provider: "offline" };
let liveLabel = "OFF AIR";
let lastState = null;
const STYLE_NAMES = { hype: "Hype", calm: "Calm", tactical: "Tactical", beginner: "New to football" };

// ---------- setup ----------
async function loadOptions() {
  const [options, health] = await Promise.all([getJSON("/api/options"), getJSON("/api/health")]);
  llm = health.llm;
  voice.useNeural(Boolean(health.speech?.enabled));
  for (const code of Object.keys(options.languages)) {
    const name = LANG_NAMES[code] ?? options.languages[code];
    if (STATIC && !options.offline_languages.includes(code)) continue; // the static demo only has recorded languages
    const offline = options.offline_languages.includes(code);
    const label = offline || llm.configured ? name : `${name} ${t("(needs a model)")}`;
    $("lang").append(new Option(label, code));
  }
  // the broadcast defaults to the interface language when it is on offer
  $("lang").value = [...$("lang").options].some((o) => o.value === uiLang()) ? uiLang() : "en";
  setProvider(llm);
}

async function loadMatch(seed) {
  meta = await getJSON(`/api/match?seed=${seed}`);
  players = {};
  const follow = $("follow");
  follow.replaceChildren(new Option(t("Nobody in particular"), ""));
  for (const team of Object.values(meta.teams)) {
    const group = document.createElement("optgroup");
    group.label = team.name;
    for (const p of team.players) {
      players[p.id] = { ...p, team: team.id };
      group.append(new Option(`#${p.number} ${p.name} · ${p.position}${p.starter ? "" : " (sub)"}`, p.id));
    }
    follow.append(group);
  }
  $("homeName").textContent = meta.teams.home.name;
  $("awayName").textContent = meta.teams.away.name;
  $("homeCrest").textContent = meta.teams.home.name[0];
  $("awayCrest").textContent = meta.teams.away.name[0];
}

function setProvider(status) {
  const badge = $("providerBadge");
  const on = status.configured && !status.breaker_open;
  badge.textContent = on ? `${status.provider.toUpperCase()} · ${status.model}` : t("OFFLINE · TEMPLATES");
  badge.classList.toggle("ai", on);
  badge.title = t(on ? "Agents call a live model" : "No model configured: agents use deterministic templates");
}

$("seed").addEventListener("change", () => loadMatch(Number($("seed").value) || 0));
$("openSetup").addEventListener("click", () => $("setup").showModal());
$("setupForm").addEventListener("submit", (e) => {
  if (e.submitter?.value !== "go") return;
  const form = new FormData(e.target);
  profile = {
    seed: Number($("seed").value) || 0, lang: $("lang").value, style: form.get("style"),
    accessible: $("accessible").checked, follow: $("follow").value, club: $("club").value, speed: $("speed").value,
    start: Number($("start").value) || 0,
  };
  setGender($("gender").value);
  if (profile.accessible) setVoice(true);
  goLive();
});
$("voiceToggle").addEventListener("click", () => setVoice(!voice.enabled));

function setGender(gender) {
  voice.setGender(gender);
  $("gender").value = voice.gender;
  try {
    localStorage.setItem(GENDER_KEY, voice.gender);
  } catch {
    // not persisted; the choice still applies to this visit
  }
}

window.addEventListener("voicewarning", ({ detail: { lang, problem } }) => {
  const name = LANG_NAMES[lang] ?? lang;
  if (problem === "missing") {
    addNote(`${t("No voice in this browser speaks")} ${name}. ${t("The booth stays quiet rather than read it in another language. Microsoft Edge has free natural voices, female and male, for all 12 languages; on Windows you can also add one in Settings → Time & language → Speech.")}`);
  } else {
    addNote(`${t(problem === "only-male" ? "Only a male voice is available for" : "Only a female voice is available for")} ${name}.`);
  }
});

function setVoice(on) {
  voice.setEnabled(on);
  $("voiceToggle").setAttribute("aria-pressed", String(voice.enabled));
  $("voiceToggle").textContent = t(voice.enabled ? "🔊 Voice on" : "🔈 Voice off");
  // When the booth reads aloud, don't make screen readers announce the same lines a second time.
  $("feed").setAttribute("aria-live", voice.enabled ? "off" : "polite");
}

// ---------- broadcast ----------
function goLive() {
  source?.close();
  setUiLang(profile.lang); // a Japanese broadcast gets a Japanese interface; the picker can still change it
  resetView();
  const params = new URLSearchParams({ seed: profile.seed, lang: profile.lang, style: profile.style,
    accessible: profile.accessible, speed: profile.speed, start: profile.start });
  if (profile.follow) params.set("follow", profile.follow);
  if (profile.club) params.set("club", profile.club);
  source = openStream(params);
  playout?.stop();
  voice.interrupt();
  playout = new Playout();
  const later = (type, handle) => source.addEventListener(type, (e) => {
    const data = JSON.parse(e.data);
    playout.push(() => handle(data));
  });
  source.addEventListener("hello", (e) => onHello(JSON.parse(e.data)));
  later("event", onEvent);
  later("segment", onSegment);
  later("trace", onTrace);
  later("overlay", (data) => onOverlay(data.cue));
  source.addEventListener("error", (e) => { if (e.data) addNote(JSON.parse(e.data).message); });
  source.addEventListener("end", () => { source.close(); playout.push(() => setLive(false, "FULL TIME")); });
  let onAir = false;
  source.addEventListener("hello", () => { onAir = true; });
  source.onerror = () => {
    if (source.readyState !== EventSource.CLOSED) return;
    setLive(false, "OFF AIR");
    if (!onAir) addNote(t("Couldn't start the broadcast. The booth may be busy (too many live broadcasts); try again in a minute."));
  };
  setLive(true, "LIVE");
}

function resetView() {
  $("feed").replaceChildren();
  $("trace").replaceChildren();
  $("moments").replaceChildren();
  $("storyline").hidden = true;
  $("feedEmpty").hidden = true;
  traceSteps = 0;
  pitch.reset();
  renderCrew();
}

function setLive(on, label) {
  liveLabel = label;
  $("live").classList.toggle("on", on);
  $("liveLabel").textContent = t(label);
}

function onHello(msg) {
  setProvider(msg.llm);
  const p = msg.profile;
  const chips = [p.lang.toUpperCase(), t(STYLE_NAMES[p.style] ?? p.style), p.accessible ? t("audio-first") : null,
    p.club ? `${t("supports")} ${msg.match.teams[p.club].name}` : null,
    p.follow ? `${t("following")} ${players[p.follow]?.name ?? p.follow}` : null, `${t("seed")} ${msg.match.seed}`].filter(Boolean);
  $("profileChips").replaceChildren(...chips.map((c) => Object.assign(document.createElement("span"),
    { className: "chip", textContent: c })));
}

function onEvent({ event, state }) {
  currentMinute = event.clock / 60;
  currentPeriod = event.period;
  pitch.show(event, players, state);
  renderState(state);
  const d = event.detail ?? {};
  if (event.type === "shot" && d.ball_speed_kmh >= FAST_SHOT_KMH) {
    toast(`${t("SHOT")} · ${d.ball_speed_kmh} km/h · ${t(event.outcome.replace("_", " "))}`, true);
  } else if (event.type === "pass" && event.outcome === "complete" && d.difficulty >= KILLER_PASS) {
    toast(`${t("KILLER PASS")} · ${d.difficulty}/100`, false);
  } else if (event.type === "pass" && event.outcome === "complete" && d.pass_distance_m >= LONG_BALL_M) {
    toast(`${t("LONG BALL")} · ${Math.round(d.pass_distance_m)} m`, false);
  } else if (TOAST[event.type]) {
    toast(t(TOAST[event.type]) + (event.type === "shot" ? ` · ${t(event.outcome.replace("_", " "))}` : ""), BIG.has(event.type));
  }
}

// Same order as the server's STORY_PRIORITY: when one moment starts several storylines, show the biggest.
const STORY_PRIORITY = ["comeback", "late_winner", "late_equalizer", "turnaround", "hat_trick", "down_to_ten",
  "quick_fire", "brace", "against_the_run", "control", "chaos", "haul"];
const rank = (story) => (STORY_PRIORITY.indexOf(story.kind) + STORY_PRIORITY.length + 1) % (STORY_PRIORITY.length + 1);

function renderStoryline(state) {
  const latest = state.storylines?.at(-1);
  const story = latest && state.storylines.filter((s) => s.event_id === latest.event_id)
    .sort((a, b) => rank(a) - rank(b))[0];
  const box = $("storyline");
  if (!story) {
    box.hidden = true;
    return;
  }
  const label = Object.assign(document.createElement("b"), { textContent: `${t("STORYLINE")} · ${story.minute}` });
  box.replaceChildren(label, document.createTextNode(story.texts?.[profile?.lang] || story.en));
  box.hidden = false;
}

function renderState(state) {
  lastState = state;
  renderStoryline(state);
  $("homeScore").textContent = state.score.home;
  $("awayScore").textContent = state.score.away;
  $("minute").textContent = state.minute;
  const home = state.teams.home.possession_pct;
  $("possHome").style.width = `${home}%`;
  $("possLabel").textContent = `${home} · ${100 - home}`;
  const m = state.momentum;
  const bar = $("momentum");
  bar.className = m < 0 ? "away" : "";
  bar.style.left = m < 0 ? `${50 + m * 50}%` : "50%";
  bar.style.width = `${Math.abs(m) * 50}%`;
  $("momentumLabel").textContent = Math.abs(m) < 0.15 ? t("even") : m > 0 ? meta.teams.home.short : meta.teams.away.short;
  const rhythm = state.rhythm;
  if (rhythm) {
    $("chaos").style.left = `${rhythm.chaos}%`;
    const who = rhythm.controller ? ` · ${meta.teams[rhythm.controller].short}` : "";
    $("chaosLabel").textContent = `${t(rhythm.label)}${who}`;
    $("chaosLabel").parentElement.title = `${rhythm.changes_5min} ${t("changes of possession in 5 min")}`;
  }
  $("statsBody").replaceChildren(...STAT_ROWS.map(([key, label]) => {
    const row = document.createElement("tr");
    for (const text of [state.teams.home[key], t(label), state.teams.away[key]]) {
      row.append(Object.assign(document.createElement("td"), { textContent: text }));
    }
    return row;
  }));
  $("moments").replaceChildren(...state.key_moments.filter((k) => !["half_time", "full_time"].includes(k.type))
    .map((k) => {
      const li = document.createElement("li");
      li.className = k.team ?? "";
      const icon = { goal: "⚽", yellow_card: "🟨", red_card: "🟥", substitution: "⇄", penalty_awarded: "◎" }[k.type] ?? "•";
      li.textContent = `${k.minute} ${icon} ${(k.player ?? "").split(" ").at(-1)}`;
      li.setAttribute("aria-label", `${k.minute} ${k.type.replace("_", " ")}, ${k.player ?? ""}, ${meta.teams[k.team]?.name ?? ""}`);
      return li;
    }));
}

let toastTimer;
function toast(text, big) {
  const box = $("eventToast");
  box.textContent = text;
  box.className = `event-toast${big ? " big" : ""}`;
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.hidden = true; }, big ? 2600 : 1100);
}

// Big calls hold the picture until they have been said. Routine lines are read only when the voice is free,
// never hold the picture, and are cut off by the next big call, so the voice never runs behind the pitch.
const HOLD_IMPORTANCE = 0.5;

function onSegment(seg) {
  $("feed").prepend(segmentCard(seg, llm.model));
  while ($("feed").childElementCount > 120) $("feed").lastElementChild.remove();
  if (seg.kind === "stats" || !voice.enabled) return undefined;
  if (seg.importance >= HOLD_IMPORTANCE) return voice.speak(seg.text, seg.lang);
  if (!voice.busy) voice.speak(seg.text, seg.lang);
  return undefined;
}

// Broadcast graphics preview: renders the same overlay cues a graphics engine would receive.
const gfxTimers = {};
function showGfx(id, build, seconds) {
  const box = $(id);
  build(box);
  box.hidden = false;
  box.style.animation = "none";
  void box.offsetWidth; // restart the slide-in animation
  box.style.animation = "";
  clearTimeout(gfxTimers[id]);
  gfxTimers[id] = setTimeout(() => { box.hidden = true; }, seconds * 1000);
}

function onOverlay(cue) {
  const p = cue.payload;
  if (cue.type === "player_tag" && p.metric === "running_speed_kmh" && p.player) pitch.tag(p.player.id, p.label);
  if (cue.type === "lower_third") {
    showGfx("lowerThird", (box) => {
      box.className = `lower-third${p.player && players[p.player.id]?.team === "away" ? " away" : ""}`;
      const who = p.player ? `#${p.player.number} ${p.player.name}` : p.team;
      box.replaceChildren(Object.assign(document.createElement("b"), { textContent: `${p.title} · ${cue.at.display_minute}` }),
        Object.assign(document.createElement("strong"), { textContent: who }),
        ...p.lines.map((line) => Object.assign(document.createElement("small"), { textContent: line })));
    }, 4);
  } else if (cue.type === "stat_card") {
    showGfx("statCard", (box) => {
      const rows = p.rows.map((r) => {
        const row = document.createElement("div");
        for (const text of [r.home, r.label, r.away]) row.append(Object.assign(document.createElement("span"), { textContent: text }));
        return row;
      });
      box.replaceChildren(Object.assign(document.createElement("b"), { textContent: `${p.title} · ${cue.at.display_minute}` }), ...rows);
    }, 6);
  }
}

function addNote(message) {
  const li = Object.assign(document.createElement("li"), { className: "segment small" });
  li.textContent = `⚠ ${message}`;
  $("feed").prepend(li);
}

// ---------- control room ----------
function renderCrew() {
  $("crew").replaceChildren(...AGENTS.map(([id, name, role]) => {
    const card = document.createElement("div");
    card.className = "agent";
    card.id = `agent-${id}`;
    card.innerHTML = `<b><i></i><span></span><span class="count">0</span></b><small></small>`;
    card.querySelector("span").textContent = t(name);
    card.querySelector("small").textContent = t(role);
    card.dataset.count = "0";
    return card;
  }));
  $("traceCount").textContent = `0 ${t("steps")}`;
}

function relabelCrew() {
  for (const [id, name, role] of AGENTS) {
    const card = $(`agent-${id}`);
    if (!card) continue;
    card.querySelector("span").textContent = t(name);
    if (card.dataset.count === "0") card.querySelector("small").textContent = t(role);
  }
  $("traceCount").textContent = `${traceSteps} ${t("steps")}`;
}

const STATE_CLASS = { start: "active", done: "ok", approved: "ok", planned: "ok", cache: "ok", template: "ok",
  rejected: "bad", fallback: "fallback", dropped: "fallback" };

/** A trace line in the interface language: the backend logs a handful of fixed English patterns. */
function traceText(detail) {
  const rules = [
    [/^(\d+) facts via (model tool calls|rule-based selection)$/, (m) => `${m[1]} ${t(`facts via ${m[2]}`)}`],
    [/^(\d+) segment\(s\) reused from another viewer$/, (m) => `${m[1]} ${t("segments reused from another viewer")}`],
    [/^drafting \(attempt (\d+)\)$/, (m) => `${t("drafting, attempt")} ${m[1]}`],
    [/^(\d+)s behind live play$/, (m) => `${m[1]}s ${t("behind live play")}`],
    [/^(?:template )?adapted for (.+)$/, (m) => `${t("adapted for")} ${m[1]}`],
    [/^(\w+) → ([\w, ]+) \(importance ([\d.]+)\)$/, (m) => `${t(TOAST[m[1]] ?? (m[1] === "pass" ? "Pass" : m[1]))} → ${
      m[2].split(", ").map((kind) => t(KIND_NAMES[kind] ?? kind)).join(", ")} (${t("importance")} ${m[3]})`],
  ];
  for (const [re, render] of rules) {
    const m = detail.match(re);
    if (m) return render(m);
  }
  return t(detail);
}

function onTrace(step) {
  traceSteps += 1;
  $("traceCount").textContent = `${traceSteps} ${t("steps")}`;
  const card = $(`agent-${step.agent}`);
  if (card) {
    card.className = `agent ${STATE_CLASS[step.status] ?? ""}`;
    card.querySelector("small").textContent = traceText(step.detail);
    if (step.status !== "start") {
      card.dataset.count = String(Number(card.dataset.count) + 1);
      card.querySelector(".count").textContent = card.dataset.count;
    }
  }
  const li = document.createElement("li");
  for (const [cls, text] of [["job", step.job], ["who", t(AGENT_NAMES[step.agent] ?? step.agent)], [`st st-${step.status}`, t(step.status) + (step.ms ? ` ${step.ms}ms` : "")], ["what", traceText(step.detail)]]) {
    li.append(Object.assign(document.createElement("span"), { className: cls, textContent: text }));
  }
  li.title = step.detail;
  $("trace").prepend(li);
  while ($("trace").childElementCount > 150) $("trace").lastElementChild.remove();
}

// ---------- ask ----------
$("askForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = $("question").value.trim();
  if (!question) return;
  const answer = $("answer");
  answer.textContent = t("Checking the stats desk…");
  try {
    const data = STATIC ? staticAnswer(question)
      : await postJSON("/api/ask", { seed: profile?.seed ?? (Number($("seed").value) || 42), minute: currentMinute,
        period: currentPeriod, question, lang: profile?.lang ?? "en" });
    const text = Object.assign(document.createElement("div"), { textContent: `${data.minute} · ${data.text}` });
    answer.replaceChildren(text, segmentFoot({ ...data, verified: true, notes: [] }, llm.model));
    voice.say(data.text, profile?.lang ?? "en", true);
  } catch (err) {
    answer.textContent = `${t("Couldn't reach the booth")} (${err.message}).`;
  }
});

// In the static demo there is no server, so questions are answered from the shared state the page already has.
function staticAnswer(question) {
  const s = lastState;
  if (!s) return { text: t("Start the broadcast first."), source: "template", evidence: [], minute: "0'" };
  const q = question.toLowerCase();
  const [h, a] = [s.teams.home, s.teams.away];
  const names = [meta.teams.home.name, meta.teams.away.name];
  const labels = { possession_pct: "Possession %", shots: "Shots", shots_on_target: "On target", corners: "Corners",
    pass_accuracy_pct: "Pass accuracy %", fouls: "Fouls" };
  const named = (key) => t(labels[key]).replace(" %", "").toLowerCase(); // the stat in the interface language
  const pick = [["possession_pct", /possess|topa|ball|hakim/], ["shots_on_target", /target|isabet/], ["shots", /shot|şut/],
    ["corners", /corner|korner/], ["pass_accuracy_pct", /pass|pas/], ["fouls", /foul|faul|card|kart/]]
    .find(([key, re]) => re.test(q) || q.includes(named(key)));
  const key = pick?.[0] ?? null;
  const text = key
    ? `${names[0]}: ${h[key]}, ${names[1]}: ${a[key]} (${t(labels[key])}).`
    : `${names[0]} ${s.score.home}-${s.score.away} ${names[1]}.`;
  const evidence = key
    ? [{ id: `F-home-${key}`, label: `${names[0]} ${key}`, value: String(h[key]) },
      { id: `F-away-${key}`, label: `${names[1]} ${key}`, value: String(a[key]) }]
    : [{ id: "F-score", label: "Score", value: `${s.score.home}-${s.score.away}` }];
  return { text, source: "template", evidence, minute: s.minute };
}

// ---------- interface language ----------
$("uiLang").addEventListener("change", (e) => setUiLang(e.target.value));
window.addEventListener("uilangchange", () => {
  setVoice(voice.enabled);
  setLive($("live").classList.contains("on"), liveLabel);
  setProvider(llm);
  relabelCrew();
  if (lastState) renderState(lastState);
  const follow = $("follow");
  if (follow.options.length) follow.options[0].textContent = t("Nobody in particular");
});

// ---------- boot ----------
if (STATIC) {
  $("seed").disabled = true;
  $("staticNote").hidden = false;
}
applyStatic();
renderCrew();
await loadOptions();
await loadMatch(Number($("seed").value) || 0);
const compareView = initCompare({ voice, seed: () => profile?.seed ?? (Number($("seed").value) || 0),
  model: () => llm.model, languages: () => [...$("lang").options].map((o) => [o.value, o.textContent]) });

// Deep links, handy for demos and screenshots:
//   ?live=1&seed=119&lang=tr&style=beginner&accessible=1&start=76&speed=20&follow=H9
//   ?view=compare&seed=119&event=E0990
const params = new URLSearchParams(location.search);
if (params.has("seed")) {
  $("seed").value = params.get("seed");
  await loadMatch(Number(params.get("seed")) || 0);
}
initVision();
setGender(params.get("gender") ?? voice.gender);
if (params.get("view") === "vision") {
  document.querySelector('[data-view="vision"]').click();
} else if (params.get("view") === "compare") {
  compareView.open(params.get("event"));
} else if (params.get("live") === "1") {
  const style = params.get("style") ?? "hype";
  profile = {
    seed: Number($("seed").value) || 0, lang: params.get("lang") ?? "en", style,
    accessible: params.get("accessible") === "1", follow: params.get("follow") ?? "", club: params.get("club") ?? "",
    speed: params.get("speed") ?? "20", start: Number(params.get("start")) || 0,
  };
  $("lang").value = profile.lang;
  document.querySelector(`input[name=style][value="${CSS.escape(style)}"]`)?.click();
  $("accessible").checked = profile.accessible;
  if (profile.accessible && params.get("voice") !== "0") setVoice(true);
  goLive();
} else {
  $("setup").showModal();
}
