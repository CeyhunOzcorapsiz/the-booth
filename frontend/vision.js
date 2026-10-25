// "Video to events": a synthetic match clip, the events the pipeline detected from its pixels, and how they
// compare with what really happened in the simulation.
import { getJSON } from "./api.js";
import { t } from "./i18n.js";
import { make } from "./render.js";

const $ = (id) => document.getElementById(id);
const TOLERANCE_S = 1.0;
const KIND = { pass: "Pass", turnover: "Turnover", shot: "Shot" };

export function initVision() {
  let loaded = false;
  window.addEventListener("viewchange", (e) => {
    if (e.detail === "vision" && !loaded) {
      loaded = true;
      load();
    }
  });

  async function load() {
    const status = $("visionStatus");
    for (;;) {
      let data;
      try {
        data = await getJSON("/api/vision");
      } catch (err) {
        status.textContent = `${t("Couldn't load the clip")} (${err.message}).`;
        return;
      }
      if (data.status === "ready") {
        status.textContent = "";
        render(data);
        return;
      }
      if (data.status !== "building") {
        status.textContent = `${t("Auto-eventing is not available on this server")}: ${data.reason ?? data.status}`;
        return;
      }
      status.textContent = t("Rendering the clip and running the detector (about two minutes)…");
      await new Promise((r) => setTimeout(r, 5000));
    }
  }

  function render(data) {
    const video = $("visionVideo");
    video.src = data.video_url;
    const start = data.clip.start_minute * 60;
    const clock = (s) => {
      const total = start + s;
      return `${Math.floor(total / 60)}:${String(Math.floor(total % 60)).padStart(2, "0")}`;
    };
    renderMetrics(data.report);
    const rows = timeline(data.detections, data.truth);
    $("visionEvents").replaceChildren(...rows.map((row) => {
      const li = make("li", `vision-row ${row.status}`);
      li.tabIndex = 0;
      const what = row.detected ?? row.truth;
      const detail = what.kind === "turnover" ? "" : ` · ${what.distance_m} m · ${Math.round(what.speed_kmh)} km/h`;
      li.append(
        make("span", "when", clock(what.t)),
        make("span", "kind", t(KIND[what.kind])),
        make("span", `team ${what.team}`, what.team === "home" ? "NOR" : "EMB"),
        make("span", "detail", detail),
        make("span", `status ${row.status}`, t({ match: "✓ matched", false: "false alarm", missed: "missed" }[row.status])),
      );
      if (row.detected && row.truth && what.kind === "pass") {
        li.title = `${t("truth")}: ${row.truth.distance_m} m, ${Math.round(row.truth.speed_kmh)} km/h`;
      }
      const seek = () => { video.currentTime = Math.max(what.t - 1.5, 0); video.play().catch(() => {}); };
      li.addEventListener("click", seek);
      li.addEventListener("keydown", (e) => { if (e.key === "Enter") seek(); });
      return li;
    }));
  }

  function renderMetrics(report) {
    const rows = Object.entries(report.events).map(([kind, m]) => {
      const tr = make("tr");
      for (const v of [t(KIND[kind]), m.truth, m.detected, m.matched, pct(m.precision), pct(m.recall), m.f1 ?? "–"]) {
        tr.append(make("td", "", String(v)));
      }
      return tr;
    });
    $("visionMetrics").replaceChildren(...rows);
    $("visionExtra").textContent = [
      `${t("Pass speed error")}: ${t("median")} ${report.pass_speed_median_error_kmh ?? "–"} km/h, ${t("mean")} ${report.pass_speed_mae_kmh ?? "–"}`,
      `${t("Pass distance error")}: ${t("median")} ${report.pass_distance_median_error_m ?? "–"} m, ${t("mean")} ${report.pass_distance_mae_m ?? "–"}`,
      `${t("Camera calibration error")}: ${report.calibration_error_m} m`,
    ].join(" · ");
  }
}

const pct = (v) => (v === null || v === undefined ? "–" : `${Math.round(v * 100)}%`);

/** Merge detections and truth into one list: matched pairs, false alarms and missed events. */
function timeline(detections, truth) {
  const used = new Set();
  const rows = detections.map((d) => {
    let best = null;
    truth.forEach((e, j) => {
      if (used.has(j) || e.kind !== d.kind || e.team !== d.team) return;
      const gap = Math.abs(e.t - d.t);
      if (gap <= TOLERANCE_S && (!best || gap < best.gap)) best = { gap, j };
    });
    if (best) used.add(best.j);
    return { detected: d, truth: best ? truth[best.j] : null, status: best ? "match" : "false" };
  });
  truth.forEach((e, j) => { if (!used.has(j)) rows.push({ detected: null, truth: e, status: "missed" }); });
  return rows.sort((a, b) => (a.detected ?? a.truth).t - (b.detected ?? b.truth).t);
}
