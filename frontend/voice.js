// Reads segments aloud. Uses Azure AI Speech neural voices through the server when configured, and the
// browser's built-in speech synthesis otherwise (free, works offline). Big moments jump the queue;
// routine lines are skipped if the queue is already long.
//
// A line is only ever read by a voice of its own language: a Turkish voice reading Japanese text says the
// numbers in Turkish. When the browser has no voice for the language, the booth stays quiet and says why.
import { speakable } from "./speakable.js";

const LOCALES = { en: "en-GB", tr: "tr-TR", es: "es-ES", de: "de-DE", fr: "fr-FR", pt: "pt-BR", it: "it-IT",
  ar: "ar-SA", nl: "nl-NL", ja: "ja-JP", hi: "hi-IN", sw: "sw-KE" };

// Browsers don't say whether a voice is female or male, so it's read from the name. These are the voices
// Windows, Edge (the free "Online (Natural)" voices), macOS/iOS and Chrome ship for the 12 languages.
// Edge writes Arabic, Japanese and Hindi voice names in their own script, so those are listed as written.
const norm = (text) => text.normalize("NFKD").replace(/[\u0300-\u036f\u064b-\u065f\u0670]/g, "").toLowerCase();
const words = (list) => new Set(norm(list).split(/\s+/));
const FEMALE = words("zira hazel susan sonia libby maisie aria jenny emma ava michelle ana sara " +
  "emel seda yelda filiz elvira ximena helena laura sabina dalia paloma monica paulina katja hedda amala " +
  "denise eloise hortense julie vivienne amelie audrey francisca thalita maria luciana fernanda " +
  "elsa isabella alice federica paola zariyah salma hoda amany laila mariam colette fenna claire ellen " +
  "nanami ayumi haruka sayaka kyoko mayu aoi swara kalpana heera lekha neerja kavya zuri rehema samantha " +
  "karen moira tessa veena serena kate fiona anna petra marlene vicki ines joana lucia carmen beatriz female " +
  "زارية فاطمة ليلى أمينة سلمى رنا سناء نورا إيمان منى عائشة أمل أماني ريم مريم " +
  "七海 ななみ स्वरा");
const MALE = words("david mark george ryan thomas guy andrew brian christopher eric roger steffan ahmet " +
  "tolga cem alvaro pablo raul jorge conrad stefan killian florian henri paul remy claude " +
  "antonio daniel donato francisco diego cosimo giuseppe luca rinaldo hamed naayf maged shakir fahed " +
  "maarten frank xander arnaud keita ichiro otoya naoki madhur hemant ravi prabhat aarav rafiki daudi " +
  "alex fred oliver arthur rishi male " +
  "حامد حمدان علي إسماعيل شاكر باسل تيم فهد رامي أحمد جمال عبدالله معاذ ليث هادي صالح " +
  "圭太 けいた मधुर");

const nameWords = (voice) => norm(voice.name).split(/[^\p{L}\p{M}]+/u);

function genderOf(voice) {
  const words = nameWords(voice);
  if (words.some((w) => FEMALE.has(w))) return "female";
  if (words.some((w) => MALE.has(w))) return "male";
  // Chrome's Google voices carry no name; outside English (where they say Male/Female) they are female.
  return voice.name.startsWith("Google") ? "female" : null;
}

/** Best browser voice for a language and gender: natural over robotic, the exact locale over a cousin. */
export function pickVoice(voices, lang, gender) {
  const locale = LOCALES[lang] || lang;
  const ours = voices.filter((v) => v.lang.replace("_", "-").toLowerCase().split("-")[0] === lang);
  if (!ours.length) return { voice: null, gender: null };
  const score = (v) => (genderOf(v) === gender ? 8 : 0) + (/natural|online|neural|premium|enhanced/i.test(v.name) ? 4 : 0) +
    (v.lang.replace("_", "-") === locale ? 2 : 0) + (v.localService ? 0 : 1);
  const voice = ours.reduce((best, v) => (score(v) > score(best) ? v : best));
  return { voice, gender: genderOf(voice) };
}

export class Voice {
  constructor() {
    this.enabled = false;
    this.neural = false;
    this.gender = "female";
    this.queue = [];
    this.speaking = false;
    this.audio = null;
    this.supported = "speechSynthesis" in window;
    this.voices = this.supported ? speechSynthesis.getVoices() : [];
    this.warned = new Set();
    this.gen = 0;
    if (this.supported) speechSynthesis.addEventListener?.("voiceschanged", () => { this.voices = speechSynthesis.getVoices(); });
  }

  useNeural(on) {
    this.neural = on;
  }

  setGender(gender) {
    this.gender = gender === "male" ? "male" : "female";
    this.warned.clear();
  }

  setEnabled(on) {
    this.enabled = on && (this.supported || this.neural);
    if (!this.enabled) this.interrupt();
  }

  /** Speak a line now and resolve when it has been said: the live view holds the picture meanwhile. */
  speak(text, lang) {
    if (!this.enabled || !text) return Promise.resolve();
    this.interrupt(); // whatever was being said is about an older moment
    const gen = this.gen;
    this.speaking = true;
    return new Promise((resolve) => {
      const done = () => {
        resolve();
        if (gen !== this.gen) return; // interrupted: a newer line owns the voice now
        this.speaking = false;
        this.#next();
      };
      this.#play({ text: speakable(text, lang), lang }, done);
    });
  }

  /** Stop the current line and drop anything queued (a newer moment is on screen). */
  interrupt() {
    this.gen += 1; // end events of the cut-off line arrive later and must not touch the new one
    this.queue = [];
    if (this.supported) speechSynthesis.cancel();
    this.audio?.pause();
    this.audio = null;
    this.speaking = false;
  }

  get busy() {
    return this.speaking;
  }

  say(text, lang, important = false) {
    if (!this.enabled || !text) return;
    const item = { text: speakable(text, lang), lang };
    if (important) this.queue.unshift(item);
    else if (this.queue.length < 3) this.queue.push(item);
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
    const gen = this.gen;
    this.#play(item, () => { if (gen === this.gen) this.#done(); });
  }

  async #play(item, done) {
    if (this.neural && (await this.#playNeural(item, done))) return;
    this.#playBrowser(item, done);
  }

  async #playNeural({ text, lang }, done) {
    try {
      const res = await fetch("/api/tts", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, lang, gender: this.gender }) });
      if (!res.ok) return false;
      const url = URL.createObjectURL(await res.blob());
      const audio = new Audio(url);
      this.audio = audio;
      let finished = false;
      const end = () => { if (finished) return; finished = true; URL.revokeObjectURL(url); done(); };
      audio.onended = audio.onerror = audio.onpause = end;
      await audio.play();
      return true;
    } catch {
      return false;
    }
  }

  #warn(lang, problem) {
    const key = `${lang}:${problem}`;
    if (this.warned.has(key)) return;
    this.warned.add(key);
    window.dispatchEvent(new CustomEvent("voicewarning", { detail: { lang, problem } }));
  }

  #playBrowser({ text, lang }, done) {
    if (!this.supported) return done();
    if (!this.voices.length) this.voices = speechSynthesis.getVoices();
    const { voice, gender } = pickVoice(this.voices, lang, this.gender);
    if (!voice) {
      this.#warn(lang, "missing"); // reading it with another language's voice would be wrong, numbers included
      this.queue = this.queue.filter((item) => item.lang !== lang);
      return done();
    }
    if (gender && gender !== this.gender) this.#warn(lang, `only-${gender}`);
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.voice = voice;
    utterance.lang = voice.lang;
    utterance.rate = 1.08;
    let finished = false;
    utterance.onend = utterance.onerror = () => { if (!finished) { finished = true; done(); } };
    speechSynthesis.speak(utterance);
  }
}
