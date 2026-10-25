// "Same moment, different shows": one event, several viewer profiles, side by side.
import { translate, t } from "./i18n.js";
import { getJSON, postJSON } from "./api.js";
import { make, segmentCard } from "./render.js";

const $ = (id) => document.getElementById(id);
const DEFAULTS = [
  { lang: "en", style: "hype", accessible: false, title: "Big-night fan" },
  { lang: "tr", style: "beginner", accessible: true, title: "Audio-first, new to football" },
  { lang: "en", style: "tactical", accessible: false, title: "Tactics nerd" },
];
const STYLES = [["hype", "Hype"], ["calm", "Calm"], ["tactical", "Tactical"], ["beginner", "New to football"]];

export function initCompare({ voice, seed, model, languages }) {
  const views = { live: $("liveView"), compare: $("compareView") };
  for (const button of document.querySelectorAll("[data-view]")) {
    button.addEventListener("click", () => {
      for (const [name, el] of Object.entries(views)) el.hidden = name !== button.dataset.view;
      for (const b of document.querySelectorAll("[data-view]")) b.setAttribute("aria-current", String(b === button));
      if (button.dataset.view === "compare") loadMoments();
    });
  }

  const columns = DEFAULTS.map((preset, i) => buildColumn(preset, i, languages()));
  $("compareColumns").replaceChildren(...columns.map((c) => c.root));
  translate($("compareColumns"));
  $("compareRun").addEventListener("click", run);
  $("comparePlay").addEventListener("click", playAll);

  let loadedSeed = null;
  let lastRun = null;
  let preferred = null;
  async function loadMoments() {
    if (loadedSeed === seed()) return;
    loadedSeed = seed();
    const list = await getJSON(`/api/moments?seed=${loadedSeed}`);
    const select = $("compareMoment");
    select.replaceChildren(...list.map((m) => new Option(m.label, m.event_id)));
    $("compareSeed").textContent = `seed ${loadedSeed}`;
    if (preferred && list.some((m) => m.event_id === preferred)) select.value = preferred;
    if (list.length) run();
  }

  async function run() {
    const eventId = $("compareMoment").value;
    if (!eventId) return;
    $("compareRun").disabled = true;
    try {
      const data = await postJSON("/api/compare", { seed: seed(), event_id: eventId, profiles: columns.map((c) => c.profile()) });
      const s = data.state;
      $("compareScore").textContent = `${s.minute} · ${s.score.home}–${s.score.away}`;
      lastRun = data;
      data.broadcasts.forEach((b, i) => columns[i].show(b, model()));
    } catch (err) {
      $("compareScore").textContent = `${t("Couldn't run the crew")} (${err.message})`;
    } finally {
      $("compareRun").disabled = false;
    }
  }

  function playAll() {
    voice.setEnabled(true);
    for (const c of columns) for (const seg of c.segments) voice.say(seg.text, seg.lang);
  }

  window.addEventListener("uilangchange", () => {
    if (lastRun) lastRun.broadcasts.forEach((b, i) => columns[i].show(b, model()));
  });

  return {
    open(eventId) {
      preferred = eventId;
      document.querySelector('[data-view="compare"]').click();
    },
  };
}

function buildColumn(preset, index, languages) {
  const root = make("section", "panel compare-col");
  const head = make("div", "compare-head");
  const title = make("h3", "", preset.title);
  const lang = make("select");
  for (const [code, name] of languages) lang.append(new Option(name, code));
  lang.value = preset.lang;
  const style = make("select");
  for (const [value, name] of STYLES) style.append(new Option(name, value));
  style.value = preset.style;
  const accessibleLabel = make("label", "inline-check");
  const accessible = make("input");
  accessible.type = "checkbox";
  accessible.checked = preset.accessible;
  accessibleLabel.append(accessible, make("span", "", "Audio-first"));
  for (const [el, name] of [[lang, "Language"], [style, "Style"]]) el.setAttribute("aria-label", `${name}, viewer ${index + 1}`);
  const controls = make("div", "compare-controls");
  controls.append(lang, style, accessibleLabel);
  head.append(title, controls);
  const feed = make("ol", "feed compare-feed");
  const trace = make("ol", "mini-trace");
  root.append(head, feed, make("div", "mini-trace-title", "Hand-offs"), trace);

  const column = {
    root,
    segments: [],
    profile: () => ({ lang: lang.value, style: style.value, accessible: accessible.checked }),
    show(broadcast, model) {
      column.segments = broadcast.segments;
      feed.replaceChildren(...(broadcast.segments.length
        ? broadcast.segments.map((s) => segmentCard(s, model))
        : [make("li", "empty", t("The director kept this viewer's booth quiet here."))]));
      trace.replaceChildren(...broadcast.trace.map((t) => {
        const li = make("li");
        li.append(make("span", "who", t.agent), make("span", `st st-${t.status}`, t.status), make("span", "what", t.detail));
        li.title = t.detail;
        return li;
      }));
    },
  };
  return column;
}
