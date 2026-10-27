// Shared rendering for on-air segments (live feed, compare view and answers).
import { t } from "./i18n.js";

export const make = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

export function segmentCard(seg, model) {
  const small = ["spatial", "explain", "stats"].includes(seg.kind);
  const li = make("li", `segment${seg.importance >= 0.9 ? " big" : ""}${small ? " small" : ""}`);
  const head = make("div", "segment-head");
  head.append(make("span", `speaker ${seg.kind}`, t(seg.speaker)), make("span", "", seg.minute));
  const text = make("div", "segment-text", seg.text);
  text.lang = seg.lang; // screen readers switch pronunciation for Turkish, Spanish, ...
  text.dir = "auto"; // an Arabic line in an English interface (or the reverse) still runs the right way
  li.append(head, text, segmentFoot(seg, model));
  return li;
}

export function segmentFoot(seg, model) {
  const foot = make("div", "segment-foot");
  if (seg.verified) foot.append(make("span", "verified", t("✓ fact-checked")));
  foot.append(make("span", `source ${seg.source}`, seg.source === "ai" ? `AI · ${model ?? "model"}` : t("template")));
  if (seg.evidence?.length) {
    const n = seg.evidence.length;
    const button = make("button", "evidence", `${n} ${t(n > 1 ? "sources" : "source")}`);
    button.type = "button";
    button.setAttribute("aria-expanded", "false");
    const list = make("ul", "evidence-detail");
    list.hidden = true;
    list.append(...seg.evidence.map((f) => make("li", "", `${f.id} · ${f.label}: ${f.value}`)));
    button.addEventListener("click", () => {
      list.hidden = !list.hidden;
      button.setAttribute("aria-expanded", String(!list.hidden));
    });
    foot.append(button, list);
  }
  for (const note of seg.notes ?? []) foot.append(make("span", "note", `⚠ ${note}`));
  return foot;
}
