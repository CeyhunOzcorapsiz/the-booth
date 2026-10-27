// Interface language: any of the 12 broadcast languages. Going live switches it to the broadcast language.
// Static text in index.html is translated by walking the page; dynamic text goes through t().
// TR doubles as the list of keys: each file in locales/ has one translation per key, in this order.
import ar from "./locales/ar.js";
import de from "./locales/de.js";
import es from "./locales/es.js";
import fr from "./locales/fr.js";
import hi from "./locales/hi.js";
import it from "./locales/it.js";
import ja from "./locales/ja.js";
import nl from "./locales/nl.js";
import pt from "./locales/pt.js";
import sw from "./locales/sw.js";

/** Each language in its own name, in the order the broadcast picker lists them. */
export const LANG_NAMES = {
  en: "English", tr: "Türkçe", es: "Español", de: "Deutsch", fr: "Français", pt: "Português", it: "Italiano",
  ar: "العربية", nl: "Nederlands", ja: "日本語", hi: "हिन्दी", sw: "Kiswahili",
};

const TR = {
  // top bar and views
  "Skip to your broadcast": "Yayına atla",
  "The Booth: a personal, fact-checked live football broadcast": "The Booth: kişisel, doğrulanmış canlı futbol yayını",
  "Live": "Canlı",
  "Same moment, 3 shows": "Aynı an, 3 yayın",
  "Video to events": "Videodan olaylar",
  "A synthetic broadcast clip, rendered from the match's tracking data. The auto-eventing pipeline sees only the pixels: it calibrates the camera from the corner flags, finds players by kit colour and the ball as a small moving white blob, tracks them, and turns changes of possession into passes, turnovers and shots, with pass distance and ball speed. Every detection is scored against what really happened.":
    "Maçın takip verisinden üretilmiş sentetik bir yayın klibi. Otomatik olay çıkarma hattı yalnızca pikselleri görür: kamerayı köşe bayraklarından kalibre eder, oyuncuları forma renginden, topu küçük ve hareketli beyaz bir leke olarak bulur, onları takip eder ve top sahipliğindeki değişimleri pas, top kaybı ve şuta çevirir; pas mesafesini ve top hızını ölçer. Her tespit gerçekte olanla karşılaştırılıp puanlanır.",
  "Detected vs. truth": "Tespit edilen ve gerçek",
  "Click an event to jump to it in the clip": "Klipte o ana gitmek için bir olaya tıkla",
  "Detection accuracy": "Tespit doğruluğu",
  "Event": "Olay", "Truth": "Gerçek", "Detected": "Tespit", "Matched": "Eşleşen", "Precision": "İsabet", "Recall": "Yakalama",
  "Pass": "Pas", "Turnover": "Top kaybı", "Shot": "Şut",
  "✓ matched": "✓ eşleşti", "false alarm": "yanlış alarm", "missed": "kaçırıldı", "truth": "gerçek",
  "Pass speed error": "Pas hızı hatası", "Pass distance error": "Pas mesafesi hatası",
  "Camera calibration error": "Kamera kalibrasyon hatası",
  "median": "ortanca", "mean": "ortalama",
  "Rendering the clip and running the detector (about two minutes)…": "Klip üretiliyor ve tespit çalışıyor (yaklaşık iki dakika)…",
  "Auto-eventing is not available on this server": "Bu sunucuda otomatik olay çıkarma yok",
  "Couldn't load the clip": "Klip yüklenemedi",
  "Synthetic match clip": "Sentetik maç klibi",
  "Your broadcast ⚙": "Yayının ⚙",
  "Model provider": "Model sağlayıcı",
  "LIVE": "CANLI",
  "OFF AIR": "YAYIN DIŞI",
  "FULL TIME": "MAÇ SONU",
  "OFFLINE · TEMPLATES": "ÇEVRİMDIŞI · ŞABLON",
  "Agents call a live model": "Ajanlar canlı bir model kullanıyor",
  "No model configured: agents use deterministic templates": "Model yok: ajanlar kural tabanlı şablonlar kullanıyor",
  // match panel
  "Match": "Maç",
  "Possession": "Topa sahip olma",
  "Momentum": "Momentum",
  "even": "dengeli",
  "Control ↔ Chaos": "Kontrol ↔ Kaos",
  "controlled": "kontrollü",
  "open": "açık",
  "chaotic": "kaotik",
  "changes of possession in 5 min": "top kaybı / 5 dk",
  "Changes of possession in the last five minutes": "Son beş dakikada topun el değiştirme sayısı",
  "STORYLINE": "HİKÂYE",
  "NORTHSTAR ATTACK →": "NORTHSTAR HÜCUM YÖNÜ →",
  "SYNTHETIC EVENTS + TRACKING · 1 HZ": "SENTETİK OLAY + TAKİP VERİSİ · 1 HZ",
  "Distance (km)": "Koşu mesafesi (km)",
  "Sprints": "Sprint",
  "Key moments": "Önemli anlar",
  "Team statistics": "Takım istatistikleri",
  "Possession %": "Topa sahip olma %",
  "Shots": "Şut",
  "On target": "İsabetli şut",
  "Corners": "Korner",
  "Passes": "Pas",
  "Fouls": "Faul",
  "Yellow cards": "Sarı kart",
  "Saves": "Kurtarış",
  "Fastest shot (km/h)": "En hızlı şut (km/sa)",
  "Pass accuracy %": "Pas isabeti %",
  "Avg pass difficulty (0-100)": "Ort. pas zorluğu (0-100)",
  "KILLER PASS": "KİLİT PAS",
  "LONG BALL": "UZUN TOP",
  // event toasts
  "GOAL": "GOL", "SHOT": "ŞUT", "CORNER": "KORNER", "FOUL": "FAUL", "YELLOW CARD": "SARI KART",
  "RED CARD": "KIRMIZI KART", "PENALTY": "PENALTI", "OFFSIDE": "OFSAYT", "SUBSTITUTION": "OYUNCU DEĞİŞİKLİĞİ",
  "KICK-OFF": "SANTRA", "HALF TIME": "İLK YARI SONU", "FREE KICK": "SERBEST VURUŞ",
  "saved": "kurtarıldı", "off target": "dışarı", "blocked": "bloke", "goal": "gol",
  // feed
  "Your broadcast": "Senin yayının",
  "Read the broadcast aloud": "Yayını sesli oku",
  "🔈 Voice off": "🔈 Ses kapalı",
  "🔊 Voice on": "🔊 Ses açık",
  "Broadcast lines, newest first": "Yayın satırları, en yenisi üstte",
  "Set up your broadcast to go live.": "Canlı yayına başlamak için yayınını kur.",
  "audio-first": "sesli mod",
  "following": "takip:",
  "seed": "seed",
  "✓ fact-checked": "✓ doğrulandı",
  "template": "şablon",
  "source": "kaynak",
  "sources": "kaynak",
  "Play-by-play": "Spiker",
  "Analyst": "Yorumcu",
  "Stats desk": "İstatistik masası",
  "Guide": "Rehber",
  "Recap editor": "Özet editörü",
  "Couldn't start the broadcast. The booth may be busy (too many live broadcasts); try again in a minute.":
    "Yayın başlatılamadı. Stüdyo meşgul olabilir (çok fazla canlı yayın); bir dakika sonra tekrar dene.",
  // control room
  "Control room": "Kontrol odası",
  "Every agent hand-off, live": "Ajanlar arası her adım, canlı",
  "steps": "adım",
  "Agent hand-off log": "Ajan adım kaydı",
  "Director": "Yönetmen", "plans what airs": "neyin yayınlanacağına karar verir",
  "Stats producer": "İstatistik yapımcısı", "tool calls → facts": "tool çağrıları → gerçekler",
  "the call": "anlatım",
  "context & colour": "bağlam ve yorum",
  "Storyline": "Hikâye", "remembers the match": "maçı hatırlar",
  "Fact-checker": "Doğrulayıcı", "traces every claim": "her iddiayı veriye bağlar",
  "Localizer": "Yerelleştirici", "your language": "senin dilin",
  "rules & pitch location": "kurallar ve sahadaki konum",
  "half & full time": "devre ve maç sonu",
  // ask
  "Ask the booth": "Stüdyoya sor",
  "Answered from the stats desk at the minute you're watching": "İzlediğin dakikadaki istatistiklerle yanıtlanır",
  "Who's had more of the ball?": "Topa kim daha çok sahip oldu?",
  "Ask": "Sor",
  "Checking the stats desk…": "İstatistik masasına bakılıyor…",
  "Couldn't reach the booth": "Stüdyoya ulaşılamadı",
  "Start the broadcast first.": "Önce yayını başlat.",
  "Static demo: pre-recorded broadcasts of match 119 on GitHub Pages, without a server or model. Run the full app locally or on Azure: see the README.":
    "Statik demo: 119 numaralı maçın önceden kaydedilmiş yayınları, sunucu ve model olmadan GitHub Pages'te. Uygulamanın tamamı için README'ye bak.",
  // compare
  "Same moment, three shows": "Aynı an, üç yayın",
  "One event from the match. Each viewer gets their own crew, and every line is fact-checked.":
    "Maçtan tek bir an. Her izleyicinin kendi ekibi var ve her satır doğrulanıyor.",
  "Moment": "An",
  "Run the crews": "Ekipleri çalıştır",
  "▶ Hear them": "▶ Dinle",
  "Big-night fan": "Büyük maç taraftarı",
  "Audio-first, new to football": "Sesli mod, futbola yeni",
  "Tactics nerd": "Taktik meraklısı",
  "Audio-first": "Sesli mod",
  "Hand-offs": "Adımlar",
  "The director kept this viewer's booth quiet here.": "Yönetmen bu izleyici için burada sessiz kalmayı seçti.",
  "Couldn't run the crew": "Ekip çalıştırılamadı",
  "Language": "Dil",
  "Style": "Stil",
  // footer and setup
  "All clubs, players and events are synthetic and generated from a seed. No real match data is used.":
    "Tüm kulüpler, oyuncular ve olaylar sentetiktir ve bir seed'den üretilir. Gerçek maç verisi kullanılmaz.",
  "Build your broadcast": "Yayınını kur",
  "Every viewer gets their own crew: same match, different show.": "Her izleyicinin kendi ekibi var: aynı maç, farklı yayın.",
  "Commentary style": "Anlatım stili",
  "Hype": "Coşkulu", "Big-night energy": "Büyük maç enerjisi",
  "Calm": "Sakin", "Radio-style, clear": "Radyo gibi, net",
  "Tactical": "Taktik", "Space, shape, stats": "Alan, diziliş, istatistik",
  "New to football": "Futbola yeni", "Rules explained": "Kurallar anlatılır",
  "Audio-first mode": "Sesli mod",
  "For blind and low-vision fans: describes where the ball is and reads everything aloud.":
    "Görme engelli ve az gören taraftarlar için: topun nerede olduğunu anlatır ve her şeyi sesli okur.",
  "Follow a player": "Bir oyuncuyu takip et",
  "Favorite club": "Tuttuğun takım",
  "No favorite": "Yok",
  "supports": "taraftar:",
  "Nobody in particular": "Kimseyi",
  "Match seed": "Maç seed'i",
  "Start at minute": "Başlangıç dakikası",
  "Speed": "Hız",
  "Cancel": "Vazgeç",
  "Go live": "Yayına başla",
  "(needs a model)": "(model gerekir)",
  // control room trace
  "start": "başladı",
  "done": "tamam",
  "planned": "planlandı",
  "cache": "önbellek",
  "approved": "onaylandı",
  "rejected": "reddedildi",
  "fallback": "yedek",
  "dropped": "atlandı",
  "pulling context with tools": "araçlarla bağlam toplanıyor",
  "facts via model tool calls": "gerçek, model tool çağrılarıyla",
  "facts via rule-based selection": "gerçek, kural tabanlı seçimle",
  "template numbers and names traced to data": "şablondaki sayı ve isimler veriye bağlandı",
  "segments reused from another viewer": "segment başka izleyiciden yeniden kullanıldı",
  "drafting, attempt": "taslak yazılıyor, deneme",
  "behind live play": "canlı oyunun gerisinde",
  "adapted for": "uyarlandı:",
  "importance": "önem",
  "tackle": "top kapma",
  "interception": "araya girme",
  // voice
  "Commentator voice": "Spiker sesi",
  "Female": "Kadın",
  "Male": "Erkek",
  "No voice in this browser speaks": "Bu tarayıcıda şu dilde ses yok:",
  "The booth stays quiet rather than read it in another language. Microsoft Edge has free natural voices, female and male, for all 12 languages; on Windows you can also add one in Settings → Time & language → Speech.": "Stüdyo, yayını başka bir dilin sesiyle okumak yerine sessiz kalıyor. Microsoft Edge'de 12 dilin hepsi için ücretsiz, doğal kadın ve erkek sesleri var; Windows'ta Ayarlar → Saat ve dil → Konuşma bölümünden de ses ekleyebilirsin.",
  "Only a male voice is available for": "Bu dil için yalnızca erkek sesi var:",
  "Only a female voice is available for": "Bu dil için yalnızca kadın sesi var:",
};
const RTL = new Set(["ar"]);
const KEYS = Object.keys(TR);
const zip = (values, code) => {
  if (values.length !== KEYS.length) console.error(`locales/${code}.js has ${values.length} entries, expected ${KEYS.length}`);
  return Object.fromEntries(KEYS.map((key, i) => [key, values[i]]));
};
const DICT = { tr: TR, ...Object.fromEntries(Object.entries({ es, de, fr, pt, it, nl, ar, ja, hi, sw }).map(([k, v]) => [k, zip(v, k)])) };
const ATTRS = ["placeholder", "aria-label", "title"];
const KEY = "booth.uiLang";

function initial() {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved in LANG_NAMES) return saved;
  } catch {
    // storage blocked: start in English
  }
  // English until the viewer picks a language (or goes live in one); the browser's language is not a choice.
  return "en";
}

let lang = initial();

export const uiLang = () => lang;
export const t = (en) => DICT[lang]?.[en] || en;

export function translate(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node.__en === undefined) {
      const text = node.nodeValue.trim();
      if (!text || !(text in TR)) continue;
      node.__en = text;
    }
    node.nodeValue = node.nodeValue.replace(node.__current ?? node.__en, t(node.__en));
    node.__current = t(node.__en);
  }
  for (const el of root.querySelectorAll("*")) {
    for (const attr of ATTRS) {
      const key = `en${attr.replace(/-./g, (m) => m[1].toUpperCase())}`;
      const value = el.dataset[key] ?? el.getAttribute(attr);
      if (value === null || !(value in TR)) continue;
      el.dataset[key] = value;
      el.setAttribute(attr, t(value));
    }
  }
}

export function applyStatic() {
  document.documentElement.lang = lang;
  document.documentElement.dir = RTL.has(lang) ? "rtl" : "ltr";
  translate(document.body);
  const picker = document.getElementById("uiLang");
  if (picker && !picker.options.length) {
    for (const [code, name] of Object.entries(LANG_NAMES)) picker.append(new Option(name, code));
  }
  if (picker) picker.value = lang;
}

export function setUiLang(next) {
  if (!(next in LANG_NAMES) || next === lang) return;
  lang = next;
  try {
    localStorage.setItem(KEY, next);
  } catch {
    // not persisted; the choice still applies to this visit
  }
  applyStatic();
  window.dispatchEvent(new CustomEvent("uilangchange", { detail: next }));
}
