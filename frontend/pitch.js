// Draws the ball, the players involved in the latest event and a short trail of recent actions.
const NS = "http://www.w3.org/2000/svg";
const TRAIL = 24;

const el = (name, attrs = {}) => {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
};

export class Pitch {
  constructor(svg, colors) {
    this.svg = svg;
    this.colors = colors;
    this.ball = svg.querySelector("#ball");
    this.line = svg.querySelector("#actionLine");
    this.actors = svg.querySelector("#actors");
    this.trail = svg.querySelector("#trail");
    this.moveBall(52.5, 34);
  }

  moveBall(x, y) {
    this.ball.style.transform = `translate(${x}px, ${y}px)`;
  }

  reset() {
    this.trail.replaceChildren();
    this.actors.replaceChildren();
    this.line.setAttribute("x2", this.line.getAttribute("x1"));
    this.moveBall(52.5, 34);
  }

  show(event, players) {
    const hasEnd = event.end_x !== null && event.end_x !== undefined;
    const endX = hasEnd ? event.end_x : event.x;
    const endY = hasEnd ? event.end_y : event.y;
    this.line.setAttribute("x1", event.x);
    this.line.setAttribute("y1", event.y);
    this.line.setAttribute("x2", endX);
    this.line.setAttribute("y2", endY);
    this.line.classList.toggle("shot", event.type === "shot");
    this.moveBall(endX, endY);

    if (event.team) {
      const dot = el("circle", { cx: event.x, cy: event.y, r: 0.55, class: "trail-dot", fill: this.colors[event.team] });
      this.trail.append(dot);
      while (this.trail.childElementCount > TRAIL) this.trail.firstElementChild.remove();
    }

    this.actors.replaceChildren();
    const actor = players[event.player];
    if (actor && !["substitution"].includes(event.type)) this.actors.append(this.#actor(actor, event.x, event.y));
    const target = players[event.target];
    if (target && hasEnd && event.type === "pass") this.actors.append(this.#actor(target, endX, endY));
  }

  #actor(player, x, y) {
    const g = el("g", { class: "actor" });
    g.append(
      el("circle", { cx: x, cy: y - 2.6, r: 1.7, fill: this.colors[player.team] }),
      Object.assign(el("text", { x, y: y - 2.55 }), { textContent: player.number }),
      Object.assign(el("text", { x, y: y - 5.1, class: "label" }), { textContent: player.name.split(" ").at(-1) }),
    );
    return g;
  }
}
