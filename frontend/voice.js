// Reads segments aloud with the browser's built-in speech synthesis (free, works offline).
// Big moments jump the queue; routine lines are skipped if the queue is already long.
const LOCALES = { en: "en-GB", tr: "tr-TR", es: "es-ES", de: "de-DE", fr: "fr-FR", pt: "pt-BR", it: "it-IT",
  ar: "ar-SA", nl: "nl-NL", ja: "ja-JP", hi: "hi-IN", sw: "sw-KE" };

export class Voice {
  constructor() {
    this.enabled = false;
    this.queue = [];
    this.speaking = false;
    this.supported = "speechSynthesis" in window;
  }

  setEnabled(on) {
    this.enabled = on && this.supported;
    if (!this.enabled) {
      this.queue = [];
      if (this.supported) speechSynthesis.cancel();
      this.speaking = false;
    }
  }

  say(text, lang, important = false) {
    if (!this.enabled || !text) return;
    if (important) this.queue.unshift({ text, lang });
    else if (this.queue.length < 3) this.queue.push({ text, lang });
    this.#next();
  }

  #next() {
    if (this.speaking || !this.queue.length) return;
    const { text, lang } = this.queue.shift();
    const utterance = new SpeechSynthesisUtterance(text.replace(/^\d+(\+\d+)?'\s*/, ""));
    utterance.lang = LOCALES[lang] || lang;
    const voice = speechSynthesis.getVoices().find((v) => v.lang === utterance.lang)
      || speechSynthesis.getVoices().find((v) => v.lang.startsWith(lang));
    if (voice) utterance.voice = voice;
    utterance.rate = 1.08;
    this.speaking = true;
    utterance.onend = utterance.onerror = () => { this.speaking = false; this.#next(); };
    speechSynthesis.speak(utterance);
  }
}
