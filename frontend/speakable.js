// Turns an on-screen broadcast line into what a commentator in that language would say out loud.
// Screens show "Northstar FC 0-2 Ember Athletic", "39.8 m", "%62", "45+3'", "99/100" and "km/h"; a voice
// reading those literally says "minus", "point", or spells symbols in the wrong language. Each language
// gets its own words for scores, units, percentages and abbreviations, and its own decimal separator.

// `to` joins a score ("2 a 1"); empty means the language just says the two numbers.
const RULES = {
  en: { to: "to", plus: "plus", percent: (n) => `${n} percent`, of: (n, d) => `${n} out of ${d}`, m: "metres",
    km: "kilometres", kmh: "kilometres per hour", comma: false },
  tr: { to: "", plus: "artı", percent: (n) => `yüzde ${n}`, of: (n, d) => `${d} üzerinden ${n}`, m: "metre",
    km: "kilometre", kmh: "kilometre hızla", comma: true },
  es: { to: "a", plus: "más", percent: (n) => `${n} por ciento`, of: (n, d) => `${n} sobre ${d}`, m: "metros",
    km: "kilómetros", kmh: "kilómetros por hora", comma: true },
  de: { to: "zu", plus: "plus", percent: (n) => `${n} Prozent`, of: (n, d) => `${n} von ${d}`, m: "Meter",
    km: "Kilometer", kmh: "Kilometer pro Stunde", comma: true },
  fr: { to: "à", plus: "plus", percent: (n) => `${n} pour cent`, of: (n, d) => `${n} sur ${d}`, m: "mètres",
    km: "kilomètres", kmh: "kilomètres heure", comma: true },
  pt: { to: "a", plus: "mais", percent: (n) => `${n} por cento`, of: (n, d) => `${n} de ${d}`, m: "metros",
    km: "quilômetros", kmh: "quilômetros por hora", comma: true },
  it: { to: "a", plus: "più", percent: (n) => `${n} per cento`, of: (n, d) => `${n} su ${d}`, m: "metri",
    km: "chilometri", kmh: "chilometri orari", comma: true },
  nl: { to: "", plus: "plus", percent: (n) => `${n} procent`, of: (n, d) => `${n} van de ${d}`, m: "meter",
    km: "kilometer", kmh: "kilometer per uur", comma: true },
  ar: { to: "مقابل", plus: "زائد", percent: (n) => `${n} بالمئة`, of: (n, d) => `${n} من ${d}`, m: "متر",
    km: "كيلومتر", kmh: "كيلومتر في الساعة", comma: false },
  ja: { to: "対", plus: "プラス", percent: (n) => `${n}パーセント`, of: (n, d) => `${d}点中${n}点`, m: "メートル",
    km: "キロメートル", kmh: "キロ", comma: false },
  hi: { to: "", plus: "प्लस", percent: (n) => `${n} प्रतिशत`, of: (n, d) => `${d} में से ${n}`, m: "मीटर",
    km: "किलोमीटर", kmh: "किलोमीटर प्रति घंटा", comma: false },
  sw: { to: "kwa", plus: "na", percent: (n) => `asilimia ${n}`, of: (n, d) => `${n} kati ya ${d}`, m: "mita",
    km: "kilomita", kmh: "kilomita kwa saa", comma: false },
};

// Abbreviations read letter by letter, the way each language names its letters.
const LETTERS = {
  en: { F: "F", C: "C", A: "A", K: "K", P: "P" },
  tr: { F: "fe", C: "ce", A: "a", K: "ke", P: "pe" },
  es: { F: "efe", C: "ce", A: "a", K: "ka", P: "pe" },
  de: { F: "ef", C: "tse", A: "a", K: "ka", P: "pe" },
  fr: { F: "èf", C: "cé", A: "a", K: "ka", P: "pé" },
  pt: { F: "efe", C: "cê", A: "a", K: "cá", P: "pê" },
  it: { F: "effe", C: "ci", A: "a", K: "cappa", P: "pi" },
  nl: { F: "ef", C: "see", A: "aa", K: "kaa", P: "pee" },
  ar: { F: "إف", C: "سي", A: "إيه", K: "كيه", P: "بي" },
  ja: { F: "エフ", C: "シー", A: "エー", K: "ケー", P: "ピー" },
  hi: { F: "एफ़", C: "सी", A: "ए", K: "के", P: "पी" },
  sw: { F: "ef", C: "si", A: "ei", K: "kei", P: "pi" },
};

const UNIT = {
  kmh: /(\d)\s*(?:km\/h|km\/saa|km\/sa|km\/u|किमी\/घं|كم\/س)/g,
  km: /(\d)\s*(?:km|किमी|كم)(?![A-Za-z/])/g,
  m: /(\d)\s*m(?![A-Za-z/])/g,
};

function spell(word, lang) {
  const letters = LETTERS[lang] ?? LETTERS.en;
  return [...word].map((ch) => letters[ch] ?? ch).join(lang === "ja" ? "" : " ");
}

export function speakable(text, lang) {
  const r = RULES[lang] ?? RULES.en;
  let out = text
    .replace(/^\d+(\+\d+)?'\s*/, "") // the minute is already on screen and in the lower third
    .replace(/[()]/g, ", ")
    .replace(/(\d+)\+(\d+)'/g, `$1 ${r.plus} $2`)
    .replace(/(\d+)'/g, "$1")
    .replace(/(\d+)\/(\d+)/g, (_, n, d) => r.of(n, d))
    .replace(/%\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*%/g, (_, a, b) => r.percent(a ?? b))
    .replace(UNIT.kmh, `$1 ${r.kmh}`)
    .replace(UNIT.km, `$1 ${r.km}`)
    .replace(UNIT.m, `$1 ${r.m}`)
    .replace(/(\d+)\s*-\s*(\d+)/g, `$1 ${r.to} $2`)
    .replace(/\b(FC|AFC|PK)\b/g, (w) => spell(w, lang))
    .replace(/[·→↔|]/g, ", ")
    .replace(/([!！]){2,}/g, "$1");
  if (r.comma) out = out.replace(/(\d)\.(\d)/g, "$1,$2");
  return out
    .replace(/([.!?。！])\s*,\s*/g, "$1 ")
    .replace(/\s*,\s*(,\s*)+/g, ", ")
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([.,!?。、])/g, "$1")
    .replace(/,([.!?。！])/g, "$1")
    .replace(/^[\s,]+|[\s,]+$/g, "");
}
