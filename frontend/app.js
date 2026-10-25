import { Pitch } from "./pitch.js";
import { Voice } from "./voice.js";
import { initCompare } from "./compare.js";
import { segmentCard, segmentFoot } from "./render.js";
import { applyStatic, setUiLang, t, uiLang } from "./i18n.js";

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
const BIG = new Set(["goal", "red_card", "penalty_awarded", "half_time", "full_time"]);
const TOAST = { goal: "GOAL", shot: "SHOT", corner: "CORNER", foul: "FOUL", yellow_card: "YELLOW CARD",
  red_card: "RED CARD", penalty_awarded: "PENALTY", offside: "OFFSIDE", substitution: "SUBSTITUTION",
  kickoff: "KICK-OFF", half_time: "HALF TIME", full_time: "FULL TIME", free_kick: "FREE KICK" };
const STAT_ROWS = [["possession_pct", "Possession %"], ["shots", "Shots"], ["shots_on_target", "On target"],
  ["fastest_shot_kmh", "Fastest shot (km/h)"], ["corners", "Corners"], ["passes", "Passes"],
  ["pass_accuracy_pct", "Pass accuracy %"], ["avg_pass_difficulty", "Avg pass difficulty (0-100)"],
  ["fouls", "Fouls"], ["yellow_cards", "Yellow cards"], ["saves", "Saves"]];
// Thresholds for metric call-outs (the brief's "indicators triggered when predefined thresholds are reached").
const FAST_SHOT_KMH = 100;
const LONG_BALL_M = 45;
const KILLER_PASS = 80;

const voice = new Voice();
const pitch = new Pitch($("pitch"), COLORS);
let source = null;
let players = {};
let meta = null;
let currentMinute = 0;
let currentPeriod = 1;
let profile = null;
let traceSteps = 0;
let llm = { provider: "offline" };
let liveLabel = "OFF AIR";
let lastState = null;
const STYLE_NAMES = { hype: "Hype", calm: "Calm", tactical: "Tactical", beginner: "New to football" };

// ---------- setup ----------
async function loadOptions() {
  const [options, health] = await Promise.all([fetch("/api/options").then((r) => r.json()),
    fetch("/api/health").then((r) => r.json())]);
  llm = health.llm;
  voice.useNeural(Boolean(health.speech?.enabled));
  for (const [code, name] of Object.entries(options.languages)) {
    const offline = options.offline_languages.includes(code);
    const label = offline || llm.configured ? name : `${name} ${t("(needs a model)")}`;
    $("lang").append(new Option(label, code));
  }
  $("lang").value = uiLang() === "tr" ? "tr" : "en"; // a Turkish interface defaults to a Turkish broadcast
  setProvider(llm);
}

async function loadMatch(seed) {
  meta = await fetch(`/api/match?seed=${seed}`).then((r) => r.json());
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
  if (profile.accessible) setVoice(true);
  goLive();
});
$("voiceToggle").addEventListener("click", () => setVoice(!voice.enabled));

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
  resetView();
  const params = new URLSearchParams({ seed: profile.seed, lang: profile.lang, style: profile.style,
    accessible: profile.accessible, speed: profile.speed, start: profile.start });
  if (profile.follow) params.set("follow", profile.follow);
  if (profile.club) params.set("club", profile.club);
  source = new EventSource(`/api/broadcast?${params}`);
  source.addEventListener("hello", (e) => onHello(JSON.parse(e.data)));
  source.addEventListener("event", (e) => onEvent(JSON.parse(e.data)));
  source.addEventListener("segment", (e) => onSegment(JSON.parse(e.data)));
  source.addEventListener("trace", (e) => onTrace(JSON.parse(e.data)));
  source.addEventListener("error", (e) => { if (e.data) addNote(JSON.parse(e.data).message); });
  source.addEventListener("end", () => { source.close(); setLive(false, "FULL TIME"); });
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
    p.follow ? `${t("following")} ${players[p.follow]?.name ?? p.follow}` : null, `seed ${msg.match.seed}`].filter(Boolean);
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
  box.replaceChildren(label, document.createTextNode(profile?.lang === "tr" ? story.tr : story.en));
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

function onSegment(seg) {
  $("feed").prepend(segmentCard(seg, llm.model));
  while ($("feed").childElementCount > 120) $("feed").lastElementChild.remove();
  if (seg.kind !== "stats") voice.say(seg.text, seg.lang, seg.importance >= 0.9);
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

function onTrace(step) {
  traceSteps += 1;
  $("traceCount").textContent = `${traceSteps} ${t("steps")}`;
  const card = $(`agent-${step.agent}`);
  if (card) {
    card.className = `agent ${STATE_CLASS[step.status] ?? ""}`;
    card.querySelector("small").textContent = step.detail;
    if (step.status !== "start") {
      card.dataset.count = String(Number(card.dataset.count) + 1);
      card.querySelector(".count").textContent = card.dataset.count;
    }
  }
  const li = document.createElement("li");
  for (const [cls, text] of [["job", step.job], ["who", step.agent], [`st st-${step.status}`, step.status + (step.ms ? ` ${step.ms}ms` : "")], ["what", step.detail]]) {
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
    const res = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seed: profile?.seed ?? Number($("seed").value) ?? 42, minute: currentMinute, period: currentPeriod,
        question, lang: profile?.lang ?? "en" }) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const text = Object.assign(document.createElement("div"), { textContent: `${data.minute} · ${data.text}` });
    answer.replaceChildren(text, segmentFoot({ ...data, verified: true, notes: [] }, llm.model));
    voice.say(data.text, profile?.lang ?? "en", true);
  } catch (err) {
    answer.textContent = `${t("Couldn't reach the booth")} (${err.message}).`;
  }
});

// ---------- interface language ----------
$("uiLang").addEventListener("click", () => setUiLang(uiLang() === "tr" ? "en" : "tr"));
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
if (params.get("view") === "compare") {
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
