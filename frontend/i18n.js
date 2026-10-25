// Interface language (English / Turkish). Independent of the broadcast language a viewer picks.
// Static text in index.html is translated by walking the page; dynamic text goes through t().
const TR = {
  // top bar and views
  "Skip to your broadcast": "Yayına atla",
  "The Booth: a personal, fact-checked live football broadcast": "The Booth: kişisel, doğrulanmış canlı futbol yayını",
  "Live": "Canlı",
  "Same moment, 3 shows": "Aynı an, 3 yayın",
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
  "STORYLINE": "HİKÂYE",
  "NORTHSTAR ATTACK →": "NORTHSTAR HÜCUM YÖNÜ →",
  "SYNTHETIC EVENTS · OTHER PLAYERS ILLUSTRATIVE": "SENTETİK OLAYLAR · DİĞER OYUNCULAR TEMSİLİ",
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
};
const ATTRS = ["placeholder", "aria-label", "title"];
const KEY = "booth.uiLang";

function initial() {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "en" || saved === "tr") return saved;
  } catch {
    // storage blocked: fall back to the browser language
  }
  return navigator.language?.toLowerCase().startsWith("tr") ? "tr" : "en";
}

let lang = initial();

export const uiLang = () => lang;
export const t = (en) => (lang === "tr" && TR[en]) || en;

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
  translate(document.body);
  const toggle = document.getElementById("uiLang");
  if (toggle) {
    toggle.textContent = lang === "tr" ? "EN" : "TR";
    toggle.setAttribute("aria-label", lang === "tr" ? "Switch interface to English" : "Arayüzü Türkçe yap");
  }
}

export function setUiLang(next) {
  lang = next;
  try {
    localStorage.setItem(KEY, next);
  } catch {
    // not persisted; the choice still applies to this visit
  }
  applyStatic();
  window.dispatchEvent(new CustomEvent("uilangchange", { detail: next }));
}
