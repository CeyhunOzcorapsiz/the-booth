// Talks to the server, or, in the static demo (GitHub Pages), to pre-recorded broadcasts.
//
// The static build (python -m booth.static_site) records the demo match for a set of viewer profiles. The
// match timeline (events + shared state) is stored once; each profile only stores its own segments, traces
// and overlay cues, keyed by the timeline index they followed. StaticStream replays them on the match clock
// with the same pacing as the server, behind the same interface as EventSource.

export const STATIC = document.documentElement.dataset.static === "1";

let manifest = null;
async function staticManifest() {
  manifest ??= await fetch("data/manifest.json").then((r) => r.json());
  return manifest;
}

const profileKey = (p) => `${p.lang}-${p.style}-${p.accessible ? 1 : 0}-${p.club || "none"}`;

/** The recorded profile closest to what the viewer asked for. */
export async function nearestProfile(p) {
  const { profiles } = await staticManifest();
  const keys = new Set(profiles.map(profileKey));
  const lang = profiles.some((x) => x.lang === p.lang) ? p.lang : "en";
  for (const candidate of [
    { ...p, lang },
    { ...p, lang, club: "" },
    { ...p, lang, accessible: false, club: "" },
    { lang, style: "hype", accessible: false, club: "" },
    { lang: "en", style: "hype", accessible: false, club: "" },
  ]) {
    if (keys.has(profileKey(candidate))) return profiles.find((x) => profileKey(x) === profileKey(candidate));
  }
  return profiles[0];
}

export async function getJSON(path) {
  if (!STATIC) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }
  const url = new URL(path, location.href);
  const file = { "/api/options": "options", "/api/health": "health", "/api/match": "match", "/api/moments": "moments",
    "/api/vision": "vision" }[
    url.pathname
  ];
  if (!file) throw new Error(`not available in the static demo: ${url.pathname}`);
  return fetch(`data/${file}.json`).then((r) => r.json());
}

export async function postJSON(path, body) {
  if (!STATIC) {
    const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }
  if (path === "/api/compare") {
    const broadcasts = [];
    let event = null;
    let state = null;
    for (const p of body.profiles) {
      const chosen = await nearestProfile(p);
      const data = await fetch(`data/compare/${body.event_id}__${profileKey(chosen)}.json`).then((r) => r.json());
      event = data.event;
      state = data.state;
      broadcasts.push(data.broadcast);
    }
    return { event, state, broadcasts };
  }
  throw new Error(`not available in the static demo: ${path}`);
}

export function openStream(params) {
  return STATIC ? new StaticStream(params) : new EventSource(`/api/broadcast?${params}`);
}

class StaticStream {
  static CLOSED = 2;

  constructor(params) {
    this.readyState = 0;
    this.listeners = {};
    this.onerror = null;
    this.timer = null;
    this.#start(Object.fromEntries(params)).catch(() => this.#fail());
  }

  addEventListener(type, fn) {
    (this.listeners[type] ??= []).push(fn);
  }

  close() {
    this.readyState = StaticStream.CLOSED;
    clearTimeout(this.timer);
  }

  #emit(message) {
    for (const fn of this.listeners[message.type] ?? []) fn({ data: JSON.stringify(message) });
  }

  #fail() {
    this.close();
    this.onerror?.();
  }

  async #start(q) {
    const profile = await nearestProfile({
      lang: q.lang, style: q.style, accessible: q.accessible === "true", club: q.club ?? "",
    });
    const [timeline, recording] = await Promise.all([
      fetch("data/timeline.json").then((r) => r.json()),
      fetch(`data/broadcast/${profileKey(profile)}.json`).then((r) => r.json()),
    ]);
    this.readyState = 1;
    const byIndex = new Map();
    for (const message of recording.messages) {
      if (!byIndex.has(message.i)) byIndex.set(message.i, []);
      byIndex.get(message.i).push(message);
    }
    this.#emit({ ...recording.hello, profile: { ...recording.hello.profile, requested: q } });
    const speed = Number(q.speed) || 20;
    const startKey = Number(q.start) > 45 ? [2, Number(q.start) * 60] : [1, Number(q.start || 0) * 60];
    const live = (e) => e.period > startKey[0] || (e.period === startKey[0] && e.clock >= startKey[1]);
    let i = timeline.findIndex(({ event }) => live(event));
    if (i < 0) i = timeline.length;
    const step = () => {
      if (this.readyState === StaticStream.CLOSED) return;
      if (i >= timeline.length) {
        this.#emit({ type: "end", state: timeline.at(-1).state });
        this.close();
        return;
      }
      const { event, state } = timeline[i];
      this.#emit({ type: "event", event, state });
      for (const message of byIndex.get(i) ?? []) this.#emit(message);
      const next = timeline[i + 1]?.event;
      i += 1;
      const gap = next ? (next.period === event.period ? next.clock - event.clock : 3) : 0;
      this.timer = setTimeout(step, Math.min(Math.max(gap, 0) / speed, 2.5) * 1000);
    };
    step();
  }
}
