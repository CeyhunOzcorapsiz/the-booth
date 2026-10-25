import { Pitch } from "./pitch.js";
import { Voice } from "./voice.js";
import { initCompare } from "./compare.js";
import { segmentCard, segmentFoot } from "./render.js";

const $ = (id) => document.getElementById(id);
const COLORS = { home: "#c5f665", away: "#ed9e83" };
const AGENTS = [
  ["director", "Director", "plans what airs"],
  ["stats-producer", "Stats producer", "tool calls → facts"],
  ["play-by-play", "Play-by-play", "the call"],
  ["analyst", "Analyst", "context & colour"],
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
  ["corners", "Corners"], ["passes", "Passes"], ["fouls", "Fouls"], ["yellow_cards", "Yellow cards"],
  ["saves", "Saves"]];

const voice = new Voice();
const pitch = new Pitch($("pitch"), COLORS);
let source = null;
let players = {};
let meta = null;
let currentMinute = 0;
let profile = null;
let traceSteps = 0;
let llm = { provider: "offline" };

// ---------- setup ----------
async function loadOptions() {
  const [options, health] = await Promise.all([fetch("/api/options").then((r) => r.json()),
    fetch("/api/health").then((r) => r.json())]);
  llm = health.llm;
  for (const [code, name] of Object.entries(options.languages)) {
    const offline = options.offline_languages.includes(code);
    const label = offline || llm.configured ? name : `${name} (needs a model)`;
    $("lang").append(new Option(label, code));
  }
  setProvider(llm);
}

async function loadMatch(seed) {
  meta = await fetch(`/api/match?seed=${seed}`).then((r) => r.json());
  players = {};
  const follow = $("follow");
  follow.replaceChildren(new Option("Nobody in particular", ""));
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
  badge.textContent = on ? `${status.provider.toUpperCase()} · ${status.model}` : "OFFLINE · TEMPLATES";
  badge.classList.toggle("ai", on);
  badge.title = on ? "Agents call a live model" : "No model configured: agents use deterministic templates";
}

$("seed").addEventListener("change", () => loadMatch(Number($("seed").value) || 0));
$("openSetup").addEventListener("click", () => $("setup").showModal());
$("setupForm").addEventListener("submit", (e) => {
  if (e.submitter?.value !== "go") return;
  const form = new FormData(e.target);
  profile = {
    seed: Number($("seed").value) || 0, lang: $("lang").value, style: form.get("style"),
    accessible: $("accessible").checked, follow: $("follow").value, speed: $("speed").value,
    start: Number($("start").value) || 0,
  };
  if (profile.accessible) setVoice(true);
  goLive();
});
$("voiceToggle").addEventListener("click", () => setVoice(!voice.enabled));

function setVoice(on) {
  voice.setEnabled(on);
  $("voiceToggle").setAttribute("aria-pressed", String(voice.enabled));
  $("voiceToggle").textContent = voice.enabled ? "🔊 Voice on" : "🔈 Voice off";
}

// ---------- broadcast ----------
function goLive() {
  source?.close();
  resetView();
  const params = new URLSearchParams({ seed: profile.seed, lang: profile.lang, style: profile.style,
    accessible: profile.accessible, speed: profile.speed, start: profile.start });
  if (profile.follow) params.set("follow", profile.follow);
  source = new EventSource(`/api/broadcast?${params}`);
  source.addEventListener("hello", (e) => onHello(JSON.parse(e.data)));
  source.addEventListener("event", (e) => onEvent(JSON.parse(e.data)));
  source.addEventListener("segment", (e) => onSegment(JSON.parse(e.data)));
  source.addEventListener("trace", (e) => onTrace(JSON.parse(e.data)));
  source.addEventListener("error", (e) => { if (e.data) addNote(JSON.parse(e.data).message); });
  source.addEventListener("end", () => { source.close(); setLive(false, "FULL TIME"); });
  source.onerror = () => { if (source.readyState === EventSource.CLOSED) setLive(false, "OFF AIR"); };
  setLive(true, "LIVE");
}

function resetView() {
  $("feed").replaceChildren();
  $("trace").replaceChildren();
  $("moments").replaceChildren();
  $("feedEmpty").hidden = true;
  traceSteps = 0;
  pitch.reset();
  renderCrew();
}

function setLive(on, label) {
  $("live").classList.toggle("on", on);
  $("liveLabel").textContent = label;
}

function onHello(msg) {
  setProvider(msg.llm);
  const p = msg.profile;
  const chips = [p.lang.toUpperCase(), p.style, p.accessible ? "audio-first" : null,
    p.follow ? `following ${players[p.follow]?.name ?? p.follow}` : null, `seed ${msg.match.seed}`].filter(Boolean);
  $("profileChips").replaceChildren(...chips.map((c) => Object.assign(document.createElement("span"),
    { className: "chip", textContent: c })));
}

function onEvent({ event, state }) {
  currentMinute = event.clock / 60;
  pitch.show(event, players);
  renderState(state);
  if (TOAST[event.type]) toast(TOAST[event.type] + (event.type === "shot" ? ` · ${event.outcome.replace("_", " ")}` : ""),
    BIG.has(event.type));
}

function renderState(state) {
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
  $("momentumLabel").textContent = Math.abs(m) < 0.15 ? "even" : m > 0 ? meta.teams.home.short : meta.teams.away.short;
  $("statsBody").replaceChildren(...STAT_ROWS.map(([key, label]) => {
    const row = document.createElement("tr");
    for (const text of [state.teams.home[key], label, state.teams.away[key]]) {
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
      return li;
    }));
}

let toastTimer;
function toast(text, big) {
  const t = $("eventToast");
  t.textContent = text;
  t.className = `event-toast${big ? " big" : ""}`;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, big ? 2600 : 1100);
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
    card.querySelector("span").textContent = name;
    card.querySelector("small").textContent = role;
    card.dataset.count = "0";
    return card;
  }));
  $("traceCount").textContent = "0 steps";
}

const STATE_CLASS = { start: "active", done: "ok", approved: "ok", planned: "ok", cache: "ok", template: "ok",
  rejected: "bad", fallback: "fallback", dropped: "fallback" };

function onTrace(t) {
  traceSteps += 1;
  $("traceCount").textContent = `${traceSteps} steps`;
  const card = $(`agent-${t.agent}`);
  if (card) {
    card.className = `agent ${STATE_CLASS[t.status] ?? ""}`;
    card.querySelector("small").textContent = t.detail;
    if (t.status !== "start") {
      card.dataset.count = String(Number(card.dataset.count) + 1);
      card.querySelector(".count").textContent = card.dataset.count;
    }
  }
  const li = document.createElement("li");
  for (const [cls, text] of [["job", t.job], ["who", t.agent], [`st st-${t.status}`, t.status + (t.ms ? ` ${t.ms}ms` : "")], ["what", t.detail]]) {
    li.append(Object.assign(document.createElement("span"), { className: cls, textContent: text }));
  }
  li.title = t.detail;
  $("trace").prepend(li);
  while ($("trace").childElementCount > 150) $("trace").lastElementChild.remove();
}

// ---------- ask ----------
$("askForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = $("question").value.trim();
  if (!question) return;
  const answer = $("answer");
  answer.textContent = "Checking the stats desk…";
  try {
    const res = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seed: profile?.seed ?? Number($("seed").value) ?? 42, minute: currentMinute,
        question, lang: profile?.lang ?? "en" }) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const text = Object.assign(document.createElement("div"), { textContent: `${data.minute} · ${data.text}` });
    answer.replaceChildren(text, segmentFoot({ ...data, verified: true, notes: [] }, llm.model));
    voice.say(data.text, profile?.lang ?? "en", true);
  } catch (err) {
    answer.textContent = `Couldn't reach the booth (${err.message}).`;
  }
});

// ---------- boot ----------
renderCrew();
await loadOptions();
await loadMatch(Number($("seed").value) || 0);
initCompare({ voice, seed: () => profile?.seed ?? (Number($("seed").value) || 0), model: () => llm.model,
  languages: () => [...$("lang").options].map((o) => [o.value, o.textContent]) });
$("setup").showModal();
