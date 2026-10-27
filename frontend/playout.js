// Keeps the picture and the commentator together, the way a broadcast delay does.
//
// The stream arrives on the server's clock (20× means a match minute every 3 seconds), but a commentator
// needs a few seconds per sentence. Every message is queued with its arrival time and presented with the
// same spacing it arrived with. When a step returns a promise (a big call being spoken), presentation
// holds until it resolves and everything after it shifts by that long, so the pitch, score, feed and
// control room never run ahead of what is being said. With the voice off nothing holds and the shift
// stays at zero.
export const MAX_HOLD_MS = 12_000;

export class Playout {
  constructor() {
    this.queue = [];
    this.shift = 0; // ms the show has been held so far
    this.running = false;
    this.stopped = false;
  }

  /** Queue one step; `fn` may return a promise to hold the picture until it settles. */
  push(fn) {
    if (this.stopped) return;
    this.queue.push({ fn, at: performance.now() });
    this.#run();
  }

  /** Behind the live stream by this many seconds (0 when the voice never held the picture). */
  get delay() {
    return Math.round(this.shift / 1000);
  }

  stop() {
    this.stopped = true;
    this.queue = [];
  }

  async #run() {
    if (this.running) return;
    this.running = true;
    while (this.queue.length && !this.stopped) {
      const item = this.queue[0];
      const wait = item.at + this.shift - performance.now();
      if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
      if (this.stopped) break;
      this.queue.shift();
      const started = performance.now();
      try {
        const hold = item.fn();
        if (hold?.then) {
          await Promise.race([hold, new Promise((resolve) => setTimeout(resolve, MAX_HOLD_MS))]);
          this.shift += performance.now() - started;
        }
      } catch (err) {
        console.warn("playout step failed", err);
      }
    }
    this.running = false;
  }
}
