// Coordinates are metres on a 105 x 68 m pitch. All people, teams and events are fictional.
export const PITCH = { width: 105, height: 68 };
const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
const round = n => Math.round(n * 10) / 10;
export const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
export function segmentDistance(p, a, b) {
  const dx = b.x - a.x, dy = b.y - a.y;
  const u = clamp(((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy || 1), 0, 1);
  return distance(p, { x: a.x + u * dx, y: a.y + u * dy });
}
function rng(seed) {
  let v = seed >>> 0;
  return () => { v += 0x6D2B79F5; let t = v; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}
const home = [[6,34],[32,10],[30,28],[30,43],[33,58],[49,39],[58,10],[55,42],[71,28],[60,34],[65,56]];
const away = [[100,34],[75,9],[63,22],[75,31],[78,45],[75,59],[62,49],[68,36],[53,31],[47,46],[51,15]];
const names = ['Atlas','Arda','Milo','Noah','Eren','Luca','Kai','Deniz','Leon','Alex','Emir'];
const opponents = ['Finn','Theo','Jude','Owen','Hugo','Nico','Adam','Leo','Ivo','Max','Remy'];
export const SCENARIOS = [
  { id:'decoy', title:{tr:'Görünmeyen asist',en:'The invisible assist'}, subtitle:{tr:'Bir koşu. Bir stoper. Açılan bir koridor.',en:'One run. One defender. A corridor opens.'}, pattern:{tr:'ALAN AÇAN KOŞU',en:'DECOY RUN'}, minute:'67:42', duration:16, keyTime:8, focus:'H9', recipient:'H8', defender:'A4',
    points:{H9:[[0,71,28],[3,74,23],[8,86,14],[12,88,16],[16,89,20]],A4:[[0,75,31],[3,77,27],[8,82,18],[12,84,22],[16,85,24]],H8:[[0,55,42],[3,59,40],[8,77,34],[11,85,33],[16,91,34]],H10:[[0,60,34],[5,64,34],[10,67,36],[16,75,37]],A8:[[0,68,36],[5,66,40],[10,70,42],[16,77,42]],A3:[[0,63,22],[8,66,23],[16,75,25]],A5:[[0,78,45],[8,80,46],[16,88,40]]},
    passes:[{t:0,end:2,from:'H3',to:'H10'},{t:6.8,end:8.5,from:'H10',to:'H8'},{t:11,end:12.3,from:'H8',to:'goal'}],
    events:[{t:0,type:'pass',player:'H3',target:'H10'},{t:2,type:'reception',player:'H10'},{t:3,type:'run',player:'H9'},{t:6.8,type:'pass',player:'H10',target:'H8'},{t:8.5,type:'reception',player:'H8'},{t:11,type:'shot',player:'H8'},{t:12.3,type:'goal',player:'H8'}]
  },
  { id:'third-man', title:{tr:'Üçüncü adam',en:'The third man'}, subtitle:{tr:'Pasın hedefi başka. Oyunun hedefi başka.',en:'The first pass hides the real destination.'}, pattern:{tr:'ÜÇÜNCÜ ADAM KOŞUSU',en:'THIRD-MAN RUN'}, minute:'34:16', duration:16,keyTime:8, focus:'H8',recipient:'H8',defender:'A8',
    points:{H6:[[0,49,39],[8,55,37],[16,65,36]],H10:[[0,64,27],[4,65,29],[8,68,30],[16,77,29]],H8:[[0,53,45],[4,60,41],[8,73,34],[12,84,32],[16,89,34]],H9:[[0,78,24],[8,84,19],[16,89,22]],A4:[[0,77,29],[8,81,25],[16,87,29]],A8:[[0,66,36],[4,63,33],[8,65,32],[16,76,33]],A5:[[0,79,46],[8,79,44],[16,88,38]]},
    passes:[{t:1,end:3,from:'H6',to:'H10'},{t:6,end:8,from:'H10',to:'H8'},{t:11,end:12.3,from:'H8',to:'goal'}],
    events:[{t:1,type:'pass',player:'H6',target:'H10'},{t:3,type:'reception',player:'H10'},{t:4,type:'run',player:'H8'},{t:6,type:'pass',player:'H10',target:'H8'},{t:8,type:'reception',player:'H8'},{t:11,type:'shot',player:'H8'},{t:12.3,type:'goal',player:'H8'}]
  },
  { id:'press',title:{tr:'Tuzağın anatomisi',en:'Anatomy of a trap'},subtitle:{tr:'Top kaybından önce kapanan seçenekler.',en:'The options disappear before possession does.'},pattern:{tr:'PRES TUZAĞI',en:'PRESSING TRAP'},minute:'52:08',duration:16,keyTime:8,focus:'H7',recipient:'H8',defender:'A2',
    points:{A2:[[0,69,8],[8,68,9],[16,72,12]],A4:[[0,77,28],[8,77,25],[16,81,27]],H7:[[0,60,13],[4,64,11],[8,67,10],[12,72,16],[16,76,20]],H8:[[0,59,27],[4,62,22],[8,65,16],[12,70,24],[16,77,29]],H9:[[0,76,17],[4,73,15],[8,71,10],[12,79,18],[16,86,26]],H10:[[0,58,36],[8,63,31],[16,76,33]],A3:[[0,64,24],[8,66,25],[16,73,29]]},
    passes:[{t:1,end:3,from:'A4',to:'A2'},{t:9,end:10.5,from:'H7',to:'H8'},{t:12,end:13.5,from:'H8',to:'H9'},{t:14,end:15.3,from:'H9',to:'A1'}],
    events:[{t:1,type:'pass',player:'A4',target:'A2'},{t:3,type:'reception',player:'A2'},{t:4,type:'pressure',player:'H7',target:'A2'},{t:8,type:'turnover',player:'H7'},{t:9,type:'pass',player:'H7',target:'H8'},{t:12,type:'pass',player:'H8',target:'H9'},{t:14,type:'shot',player:'H9'},{t:15.3,type:'save',player:'A1'}]
  }
];
export function scenarioById(id) { return SCENARIOS.find(s => s.id === id); }
function interpolate(points, t) {
  if(t <= points[0][0]) return {x:points[0][1],y:points[0][2]};
  for(let i=1;i<points.length;i++) if(t <= points[i][0]) {
    const a=points[i-1],b=points[i],u=(t-a[0])/(b[0]-a[0]);
    const s=u*u*(3-2*u);
    return {x:a[1]+(b[1]-a[1])*s,y:a[2]+(b[2]-a[2])*s};
  }
  return {x:points.at(-1)[1],y:points.at(-1)[2]};
}
export function generateMatch(id='decoy',seed=42) {
  const scenario=scenarioById(id);
  if(!scenario) throw new Error('Unknown scenario');
  const random=rng(seed);
  const players=[...home.map((p,i)=>({id:`H${i+1}`,team:'home',number:i+1,name:names[i],x:p[0],y:p[1]})),...away.map((p,i)=>({id:`A${i+1}`,team:'away',number:i+1,name:opponents[i],x:p[0],y:p[1]}))];
  const offsets=Object.fromEntries(players.map(p=>[p.id,{x:(random()-.5)*.7,y:(random()-.5)*.7}]));
  const frames=[];
  for(let tick=0;tick<=scenario.duration*10;tick++) {
    const t=tick/10;
    const positions=players.map(p=>{
      const pos=scenario.points[p.id]?interpolate(scenario.points[p.id],t):{x:p.x+Math.sin(t*.17+p.number)*Math.min(1,t/3),y:p.y+Math.sin(t*.23+p.number)*Math.min(.6,t/4)};
      return {id:p.id,x:round(clamp(pos.x+offsets[p.id].x,1,104)),y:round(clamp(pos.y+offsets[p.id].y,1,67))};
    });
    frames.push({t,players:positions,ball:null});
  }
  const at=(t,id)=>id==='goal'?{x:104,y:34}:frames[clamp(Math.round(t*10),0,frames.length-1)].players.find(p=>p.id===id);
  for(const f of frames) {
    const pass=scenario.passes.find(p=>f.t>=p.t&&f.t<=p.end);
    if(pass) {const a=at(pass.t,pass.from),b=at(pass.end,pass.to),u=(f.t-pass.t)/(pass.end-pass.t);f.ball={x:round(a.x+(b.x-a.x)*u),y:round(a.y+(b.y-a.y)*u)};}
    else {
      const last=scenario.passes.filter(p=>p.end<f.t).at(-1);
      const holder=id==='press'&&f.t>=8&&f.t<9?'H7':last?.to??scenario.passes[0].from;
      const p=at(f.t,holder);f.ball={x:round(p.x+.35),y:round(p.y+.25)};
    }
  }
  return {id,seed,synthetic:true,sampleRateHz:10,pitch:PITCH,teams:{home:'NORTHSTAR FC',away:'EMBER ATHLETIC'},scenario,players,frames,events:scenario.events.map((e,i)=>({...e,id:`${id}-${seed}-e${i+1}`}))};
}
export function frameAt(match,t) {return match.frames[clamp(Math.round(t*10),0,match.frames.length-1)];}
export function analyze(match) {
  const s=match.scenario,before=frameAt(match,0),after=frameAt(match,s.keyTime);
  const pos=(f,id)=>f.players.find(p=>p.id===id);
  const focus=match.players.find(p=>p.id===s.focus);
  const movement=round(distance(pos(before,s.focus),pos(after,s.focus)));
  const facts=[],overlays=[];
  let metrics,accepted;
  if(s.id==='decoy') {
    const a={x:64,y:34},b={x:80,y:34};
    const clearance=f=>Math.min(...f.players.filter(p=>p.id.startsWith('A')&&p.id!=='A1').map(p=>segmentDistance(p,a,b)));
    const start=round(clearance(before)),end=round(clearance(after));
    const displacement=round(distance(pos(before,s.defender),pos(after,s.defender)));
    accepted=end-start>3&&displacement>6;
    metrics=[{key:'clearance',value:end,unit:'m',before:start,label:{tr:'Pas koridoru açıklığı',en:'Passing-lane clearance'}},{key:'displacement',value:displacement,unit:'m',label:{tr:'Stoperin yer değiştirmesi',en:'Defender displacement'}},{key:'run',value:movement,unit:'m',label:{tr:'Koşudaki yer değiştirme',en:'Off-ball displacement'}}];
    facts.push({id:'F1',t:3,end:8,label:{tr:'9 numara dış koridora koşuyor',en:'No. 9 runs into the outside channel'},detail:{tr:`Leon ilk 8 saniyede ${movement} m yer değiştirdi.`,en:`Leon displaced ${movement} m in the first 8 seconds.`}},
      {id:'F2',t:5,end:8,label:{tr:'Stoper dışarı hareket ediyor',en:'The centre-back moves outward'},detail:{tr:`Owen ${displacement} m yer değiştirdi; bu hareket tek başına oyuncu niyetini kanıtlamaz.`,en:`Owen displaced ${displacement} m; motion alone does not prove intent.`}},
      {id:'F3',t:8,end:8.5,label:{tr:'İç koridorun açıklığı artıyor',en:'The inside corridor becomes clearer'},detail:{tr:`Sabit pas hattına en yakın savunmacı mesafesi ${start} m → ${end} m.`,en:`Nearest-defender distance to the fixed passing lane: ${start} m → ${end} m.`}});
    overlays.push({type:'lane',from:a,to:b},{type:'run',player:s.focus},{type:'defender',player:s.defender},{type:'space',x:76,y:34,rx:9,ry:6});
  } else if(s.id==='third-man') {
    const defender=pos(after,'A8'),receiver=pos(after,'H8');
    const separation=round(distance(receiver,defender));
    accepted=receiver.x>defender.x+4&&match.events.filter(e=>e.type==='pass'&&e.t<=8).length===2;
    metrics=[{key:'separation',value:separation,unit:'m',label:{tr:'Alıcı ile orta saha arası',en:'Receiver–midfielder gap'}},{key:'passes',value:2,unit:'',label:{tr:'Bağlantı pası',en:'Connecting passes'}},{key:'run',value:movement,unit:'m',label:{tr:'Koşudaki yer değiştirme',en:'Off-ball displacement'}}];
    facts.push({id:'F1',t:1,end:3,label:{tr:'6 numara bağlantı oyuncusunu buluyor',en:'No. 6 finds the link player'},detail:{tr:'Luca → Alex pası, olay akışında kayıtlı.',en:'Luca → Alex is recorded in the event stream.'}},
      {id:'F2',t:4,end:8,label:{tr:'8 numara savunmanın arkasına çıkıyor',en:'No. 8 moves beyond the midfielder'},detail:{tr:`Deniz ${movement} m yer değiştirerek rakip orta sahanın ilerisine geçti.`,en:`Deniz displaced ${movement} m and moved beyond the opposing midfielder.`}},
      {id:'F3',t:8,end:8.2,label:{tr:'İkinci pas üçüncü adamı buluyor',en:'The second pass finds the third man'},detail:{tr:`Alex → Deniz pasında rakip orta sahayla mesafe ${separation} m.`,en:`At the Alex → Deniz reception, midfielder separation is ${separation} m.`}});
    overlays.push({type:'run',player:'H8'},{type:'lane',from:pos(frameAt(match,6),'H10'),to:receiver},{type:'space',x:75,y:34,rx:8,ry:6});
  } else {
    const victim=pos(after,'A2');
    const distances=['H7','H8','H9'].map(id=>distance(pos(after,id),victim));
    const near=distances.filter(d=>d<9).length;
    const nearest=round(Math.min(...distances));
    accepted=near===3&&match.events.some(e=>e.type==='turnover');
    metrics=[{key:'pressers',value:near,unit:'',label:{tr:'9 metre içindeki baskıcı',en:'Pressers within 9 m'}},{key:'nearest',value:nearest,unit:'m',label:{tr:'En yakın baskıcının mesafesi',en:'Nearest presser distance'}},{key:'run',value:movement,unit:'m',label:{tr:'Baskıcının yer değiştirmesi',en:'Presser displacement'}}];
    facts.push({id:'F1',t:1,end:3,label:{tr:'Pas kenar çizgisine gidiyor',en:'The pass goes toward the touchline'},detail:{tr:'Owen → Theo pasının ardından top sağ bekte.',en:'Theo receives the pass from Owen near the touchline.'}},
      {id:'F2',t:4,end:8,label:{tr:'Üç oyuncu baskı mesafesine giriyor',en:'Three players converge'},detail:{tr:`8. saniyede ${near} oyuncu, topu alan oyuncunun 9 m yakınında.`,en:`At 8 seconds, ${near} players are within 9 m of the receiver.`}},
      {id:'F3',t:8,end:9,label:{tr:'Top kazanımı olay akışında doğrulanıyor',en:'The turnover is confirmed in the event stream'},detail:{tr:`Kai topu kazanıyor; en yakın baskı mesafesi ${nearest} m.`,en:`Kai wins possession; nearest pressure distance is ${nearest} m.`}});
    overlays.push(...['H7','H8','H9'].map(id=>({type:'pressure',player:id,to:'A2'})),{type:'space',x:68,y:9,rx:8,ry:7});
  }
  return {pattern:s.id,accepted,focus,metrics,facts,overlays,window:{start:0,end:s.keyTime},verdict:{tr:accepted?'Örüntü ölçümlerle destekleniyor':'Kanıt yetersiz',en:accepted?'Pattern supported by measurements':'Insufficient evidence'},caveat:{tr:'Sentetik bir senaryo üzerinde geometrik analizdir. Oyuncu niyeti veya gerçek maçlarda nedensellik kanıtı değildir.',en:'Geometric analysis of a synthetic scenario. It does not establish player intent or causality in real matches.'}};
}
export function narrative(match,analysis,mode='fan',lang='tr') {
  const m=analysis.metrics;
  const texts={decoy:{tr:{fan:'Gol Deniz’den, ama boşluk Leon’un koşusuyla birlikte açıldı. 9 numara dışarı hareket ederken stoper de o yöne kaydı. Deniz iç koridordan ilerledi.',analyst:`0–8 saniyede 9 numaranın yer değiştirmesi ${m[2].value} m; stoperinki ${m[1].value} m. Sabit pas hattının savunmacılara açıklığı ${m[0].before} m’den ${m[0].value} m’ye çıktı. Veriler alan açan koşu örüntüsünü destekliyor; niyet veya tek başına nedensellik göstermez.`},en:{fan:'Deniz finishes, but watch Leon. As No. 9 moves wide, the centre-back shifts with him. The inside lane opens for Deniz.',analyst:`Across 0–8 seconds, No. 9 displaced ${m[2].value} m and the centre-back ${m[1].value} m. Fixed-lane clearance increased from ${m[0].before} m to ${m[0].value} m. This supports a decoy-run pattern, without establishing intent or causality.`}},'third-man':{tr:{fan:'İlk pası Alex aldı, ama asıl boşluğa Deniz koştu. Luca’nın pası, Alex’in bağlantısı ve Deniz’in koşusu aynı hücumda birleşti.',analyst:`Luca → Alex → Deniz zincirinde üçüncü oyuncu ${m[2].value} m yer değiştirdi. İkinci pasın alındığı anda rakip orta saha ile arası ${m[0].value} m. Pas olayları ve konumlar üçüncü adam örüntüsünü birlikte destekliyor.`},en:{fan:'Alex receives the first pass, but Deniz makes the run that matters. Luca starts the move, Alex connects it, and Deniz arrives in space.',analyst:`In the Luca → Alex → Deniz sequence, the third player displaced ${m[2].value} m. At reception, the gap to the opposing midfielder is ${m[0].value} m. Pass events and positions support the third-man pattern.`}},press:{tr:{fan:'Top kaybını değil, öncesini izleyin. Theo pası aldığında üç rakip çevresinde toplandı. Kai yaklaşırken kaçış alanı daraldı ve top kazanıldı.',analyst:`Owen → Theo pasını izleyen baskı penceresinde ${m[0].value} Northstar oyuncusu alıcının 9 m yakınına girdi. En yakın baskıcı ${m[1].value} m mesafede; top kazanımı 8. saniyede olay akışında kayıtlı.`},en:{fan:'Watch the seconds before the turnover. As Theo receives, three opponents close in. Kai gets tight, and Northstar wins the ball.',analyst:`After Owen → Theo, ${m[0].value} Northstar players converge within 9 m of the receiver. The nearest presser is ${m[1].value} m away; a turnover is recorded at 8 seconds.`}}};
  return {text:texts[match.id][lang][mode],source:'local',evidenceIds:analysis.facts.map(f=>f.id)};
}
