// Draws the pitch: the ball, all 22 players and a short trail of recent actions.
//
// The data is event-level (who did what, where), not full tracking. Players involved in an event are drawn
// exactly where the event happened; everyone else is placed by their 4-3-3 slot, shifted with the ball and
// with who has possession. Those positions are illustrative, and the caption says so.
const NS = "http://www.w3.org/2000/svg";
const TRAIL = 24;
// Slot order matches the server lineup: shirts 1, 2, 3, 4, 5, 6, 8, 10, 7, 9, 11 (home attacking right).
const SHAPE = [[5, 34], [32, 58], [32, 10], [29, 26], [29, 42], [43, 34], [51, 50], [53, 18], [66, 58], [70, 34], [66, 10]];

const el = (name, attrs = {}) => {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
};
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export class Pitch {
  constructor(svg, colors) {
    this.svg = svg;
    this.colors = colors;
    this.ball = svg.querySelector("#ball");
    this.line = svg.querySelector("#actionLine");
    this.layer = svg.querySelector("#actors");
    this.trail = svg.querySelector("#trail");
    this.dots = new Map();
    this.moveBall(52.5, 34);
  }

  moveBall(x, y) {
    this.ball.style.transform = `translate(${x}px, ${y}px)`;
  }

  reset() {
    this.trail.replaceChildren();
    this.layer.replaceChildren();
    this.dots.clear();
    this.line.setAttribute("x2", this.line.getAttribute("x1"));
    this.moveBall(52.5, 34);
  }

  show(event, players, state) {
    const hasEnd = event.end_x !== null && event.end_x !== undefined;
    const endX = hasEnd ? event.end_x : event.x;
    const endY = hasEnd ? event.end_y : event.y;
    this.line.setAttribute("x1", event.x);
    this.line.setAttribute("y1", event.y);
    this.line.setAttribute("x2", endX);
    this.line.setAttribute("y2", endY);
    this.line.classList.toggle("shot", event.type === "shot");
    this.moveBall(endX, endY);

    if (event.team && event.type !== "substitution") {
      this.trail.append(el("circle", { cx: event.x, cy: event.y, r: 0.55, class: "trail-dot", fill: this.colors[event.team] }));
      while (this.trail.childElementCount > TRAIL) this.trail.firstElementChild.remove();
    }

    const pinned = {};
    if (event.type !== "substitution") {
      if (event.player) pinned[event.player] = [event.x, event.y];
      if (event.target && hasEnd && event.type === "pass") pinned[event.target] = [endX, endY];
    }
    this.#layout(state, players, endX, endY, pinned);
  }

  #layout(state, players, ballX, ballY, pinned) {
    const seen = new Set();
    for (const team of ["home", "away"]) {
      const lineup = state.on_pitch?.[team] ?? [];
      const attacking = state.possession === team;
      lineup.forEach((pid, slot) => {
        if (!pid || !players[pid]) return;
        seen.add(pid);
        const [x, y] = pinned[pid] ?? this.#slotPosition(team, slot, ballX, ballY, attacking);
        this.#place(players[pid], x, y, Boolean(pinned[pid]));
      });
    }
    for (const [pid, dot] of this.dots) {
      if (!seen.has(pid)) {
        dot.remove();
        this.dots.delete(pid);
      }
    }
  }

  #slotPosition(team, slot, ballX, ballY, attacking) {
    const [fx, fy] = SHAPE[slot];
    const flip = team === "away";
    const a = flip ? 105 - ballX : ballX; // ball position from this team's point of view
    const by = flip ? 68 - ballY : ballY;
    let x;
    let y;
    if (slot === 0) {
      x = fx + (a - 52.5) * 0.06;
      y = 34 + (by - 34) * 0.15;
    } else {
      x = fx + (a - 52.5) * 0.55 + (attacking ? 5 : -4);
      y = 34 + (fy - 34) * (attacking ? 1.05 : 0.8) + (by - 34) * 0.3;
    }
    x = clamp(x, 2, 101);
    y = clamp(y, 2, 66);
    return flip ? [105 - x, 68 - y] : [x, y];
  }

  #place(player, x, y, active) {
    let dot = this.dots.get(player.id);
    if (!dot) {
      dot = el("g", { class: "actor" });
      dot.append(
        el("circle", { r: 1.55, fill: this.colors[player.team] }),
        Object.assign(el("text", { y: 0.05 }), { textContent: player.number }),
        Object.assign(el("text", { y: -2.6, class: "label" }), { textContent: player.name.split(" ").at(-1) }),
      );
      this.layer.append(dot);
      this.dots.set(player.id, dot);
    }
    dot.classList.toggle("active", active);
    dot.style.transform = `translate(${x}px, ${y}px)`;
    if (active) this.layer.append(dot); // draw on top
  }
}
