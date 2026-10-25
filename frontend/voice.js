// Reads segments aloud. Uses Azure AI Speech neural voices through the server when configured, and the
// browser's built-in speech synthesis otherwise (free, works offline). Big moments jump the queue;
// routine lines are skipped if the queue is already long.
const LOCALES = { en: "en-GB", tr: "tr-TR", es: "es-ES", de: "de-DE", fr: "fr-FR", pt: "pt-BR", it: "it-IT",
  ar: "ar-SA", nl: "nl-NL", ja: "ja-JP", hi: "hi-IN", sw: "sw-KE" };
const clean = (text) => text.replace(/^\d+(\+\d+)?'\s*/, "");

export class Voice {
  constructor() {
    this.enabled = false;
    this.neural = false;
    this.queue = [];
    this.speaking = false;
    this.audio = null;
    this.supported = "speechSynthesis" in window;
  }

  useNeural(on) {
    this.neural = on;
  }

  setEnabled(on) {
    this.enabled = on && (this.supported || this.neural);
    if (!this.enabled) {
      this.queue = [];
      if (this.supported) speechSynthesis.cancel();
      this.audio?.pause();
      this.speaking = false;
    }
  }

  say(text, lang, important = false) {
    if (!this.enabled || !text) return;
    if (important) this.queue.unshift({ text: clean(text), lang });
    else if (this.queue.length < 3) this.queue.push({ text: clean(text), lang });
    this.#next();
  }

  #done = () => {
    this.speaking = false;
    this.#next();
  };

  async #next() {
    if (this.speaking || !this.queue.length) return;
    const item = this.queue.shift();
    this.speaking = true;
    if (this.neural && (await this.#playNeural(item))) return;
    this.#playBrowser(item);
  }

  async #playNeural({ text, lang }) {
    try {
      const res = await fetch("/api/tts", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, lang }) });
      if (!res.ok) return false;
      const url = URL.createObjectURL(await res.blob());
      this.audio = new Audio(url);
      this.audio.onended = this.audio.onerror = () => { URL.revokeObjectURL(url); this.#done(); };
      await this.audio.play();
      return true;
    } catch {
      return false;
    }
  }

  #playBrowser({ text, lang }) {
    if (!this.supported) return this.#done();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = LOCALES[lang] || lang;
    const voices = speechSynthesis.getVoices();
    const voice = voices.find((v) => v.lang === utterance.lang) || voices.find((v) => v.lang.startsWith(lang));
    if (voice) utterance.voice = voice;
    utterance.rate = 1.08;
    utterance.onend = utterance.onerror = this.#done;
    speechSynthesis.speak(utterance);
  }
}
