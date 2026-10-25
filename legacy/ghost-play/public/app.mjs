const $=id=>document.getElementById(id);
const state={match:null,scenarios:[],time:0,playing:false,speed:1,mode:'fan',lang:'tr',overlays:true,seed:42,selected:null,health:null,request:0,loading:0,recap:null};
const dictionary={
tr:{workspace:'Maç zekâsı çalışma alanı',eyebrow:'OYUNUN GÖRÜNMEYEN TARAFI',heading:'Skorun arkasındaki hikâye.',intro:'Topu izledin. Şimdi oyunu değiştiren hareketi gör.',export:'Veriyi indir',home:'EV SAHİBİ',away:'DEPLASMAN',synthetic:'SENTETİK MAÇ',fictional:'Kurgusal takımlar · 10 Hz takip',tactical:'TAKTİK TEKRAR',overlays:'Analiz katmanı',offball:'Topsuz hareket',metres:'Koordinatlar metre cinsindedir',evidenceWindow:'Analiz penceresi',keyMoment:'Kritik ana git',insight:'GHOST INSIGHT',fan:'Taraftar',analyst:'Analist',beyond:'TOPUN ÖTESİNE BAK',verified:'Konumlar + olay akışı ile kontrol edildi',chain:'KANIT ZİNCİRİ',click:'Sahada göster',recap:'Pozisyon özetini oluştur',workflow:'ANALİZ AKIŞI',transparent:'ŞEFFAF İŞLEM KAYDI',askTitle:'BU POZİSYONU SOR',askHint:'Yanıtlar bu sekansın konum ve olay verileriyle sınırlıdır.',footer:'Tüm maç verileri sentetiktir. Gerçek maç görüntüsü kullanılmaz.',ready:'STÜDYO HAZIR',recapTitle:'YAYINA HAZIR POZİSYON ÖZETİ',downloadRecap:'Özeti indir · JSON',copy:'Metni kopyala'},
en:{workspace:'Match intelligence workspace',eyebrow:'THE UNSEEN SIDE OF FOOTBALL',heading:'The story behind the score.',intro:'You watched the ball. Now see the run that changed the game.',export:'Export data',home:'HOME',away:'AWAY',synthetic:'SYNTHETIC MATCH',fictional:'Fictional teams · 10 Hz tracking',tactical:'TACTICAL REPLAY',overlays:'Analysis overlay',offball:'Off-ball movement',metres:'Coordinates in metres',evidenceWindow:'Analysis window',keyMoment:'Jump to key moment',insight:'GHOST INSIGHT',fan:'Fan',analyst:'Analyst',beyond:'LOOK BEYOND THE BALL',verified:'Checked against positions + event stream',chain:'EVIDENCE CHAIN',click:'Show on pitch',recap:'Create moment recap',workflow:'ANALYSIS WORKFLOW',transparent:'TRANSPARENT EXECUTION LOG',askTitle:'ASK ABOUT THIS MOMENT',askHint:'Answers are limited to the positions and events in this sequence.',footer:'All match data is synthetic. No real match footage is used.',ready:'STUDIO READY',recapTitle:'BROADCAST MOMENT RECAP',downloadRecap:'Download recap · JSON',copy:'Copy text'}
};
const text=(tr,en)=>state.lang==='tr'?tr:en;
const sec=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${String(Math.floor(t%60)).padStart(2,'0')}`;
const svgNS='http://www.w3.org/2000/svg';
function svg(tag,attrs={},content) {const n=document.createElementNS(svgNS,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(content!==undefined)n.textContent=content;return n;}
function node(tag,cls,content) {const n=document.createElement(tag);if(cls)n.className=cls;if(content!==undefined)n.textContent=content;return n;}
let toastTimer;
function toast(message){$('toast').textContent=message;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),4000);}
async function api(url,body,signal){const r=await fetch(url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal}:{signal});const data=await r.json();if(!r.ok)throw new Error(data.error||'Request failed');return data;}
function download(value,name){const blob=new Blob([typeof value==='string'?value:JSON.stringify(value,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=node('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function stop(){state.playing=false;$('play').textContent='▶';$('play').setAttribute('aria-label',text('Oynat','Play'));}
function labels(){
  document.documentElement.lang=state.lang;
  document.querySelectorAll('[data-i18n]').forEach(el=>el.textContent=dictionary[state.lang][el.dataset.i18n]);
  $('language').replaceChildren(document.createTextNode(state.lang.toUpperCase()+' '),node('span','','⌄'));
  $('language').setAttribute('aria-label',text('Switch to English','Türkçeye geç'));
  $('question').placeholder=text('Bu koşu neden önemli?','Why does this run matter?');
  $('connection').textContent=state.health?.aiConfigured?text('AZURE AYARLI','AZURE CONFIGURED'):text('YEREL ANALİZ','LOCAL ANALYSIS');
  $('connection').classList.toggle('cloud',Boolean(state.health?.aiConfigured));
  $('scenarioTabs').replaceChildren(...state.scenarios.map((s,i)=>{const b=node('button',`scenario-tab${s.id===state.match?.id?' selected':''}`);b.append(node('span','',String(i+1).padStart(2,'0')),document.createTextNode(s.title[state.lang]));b.setAttribute('aria-pressed',String(s.id===state.match?.id));b.onclick=()=>load(s.id);return b;}));
  document.querySelectorAll('[data-mode]').forEach(b=>{b.classList.toggle('selected',b.dataset.mode===state.mode);b.setAttribute('aria-pressed',String(b.dataset.mode===state.mode));});
  $('play').setAttribute('aria-label',state.playing?text('Duraklat','Pause'):text('Oynat','Play'));
  $('restart').setAttribute('aria-label',text('Başa dön','Restart'));
  $('scrubber').setAttribute('aria-label',text('Pozisyon zamanı','Sequence time'));
  $('speed').setAttribute('aria-label',text('Oynatma hızı','Playback speed'));
  $('pitch').setAttribute('aria-label',text('22 oyuncu ve topun hareket ettiği sentetik futbol sahası','Synthetic football pitch with 22 moving players and the ball'));
  $('closeRecap').setAttribute('aria-label',text('Kapat','Close'));
  $('askButton').setAttribute('aria-label',text('Sor','Ask'));
  document.querySelector('label[for="question"]').textContent=text('Pozisyon hakkında soru','Question about this moment');
  if(state.match)$('sequenceLabel').textContent=`${text('SEKANS','SEQUENCE')} ${String(state.scenarios.findIndex(s=>s.id===state.match.id)+1).padStart(2,'0')} / 03`;
}
let narrativeController;
async function updateNarrative(){
  narrativeController?.abort();narrativeController=new AbortController();
  const request=++state.request;
  $('sourceBadge').textContent=text('YÜKLENİYOR','LOADING');
  try {
    const result=await api('/api/narrative',{id:state.match.id,seed:state.seed,mode:state.mode,lang:state.lang},narrativeController.signal);
    if(request!==state.request)return;
    $('narrative').textContent=result.text;
    $('sourceBadge').textContent=result.source==='azure'?'AZURE AI':text('YEREL','LOCAL');
    $('citations').replaceChildren(...result.evidenceIds.map(id=>{const b=node('button','citation',`↗ ${id}`);b.setAttribute('aria-label',text(`${id} kanıtını göster`,`Show evidence ${id}`));b.onclick=()=>jumpFact(id);return b;}));
    renderWorkflow(result.source);
    if(result.warning)toast(result.warning);
  }catch(e){if(e.name==='AbortError')return;$('narrative').textContent=text('Açıklama yüklenemedi. Sunucu bağlantısını kontrol et.','Explanation unavailable. Check the server connection.');$('sourceBadge').textContent=text('BAĞLANTI HATASI','OFFLINE');}
}
function renderWorkflow(source='local'){
  const steps=[{name:text('Geometri','Geometry'),note:text('Konumları ölçer','Measures positions'),icon:'⌁'},{name:text('Kanıt kontrolü','Evidence check'),note:text('Örüntüyü sınar','Tests the pattern'),icon:'✓'},{name:source==='azure'?text('AI editör + denetçi','AI editor + reviewer'):text('Yerel anlatım','Local narrative'),note:source==='azure'?'Microsoft Foundry':text('Şablon tabanlı','Template based'),icon:'✧'}];
  const children=[];steps.forEach((s,i)=>{if(i)children.push(node('span','workflow-chevron','›'));const step=node('div','workflow-step');const description=node('div');description.append(node('strong','',s.name),node('small','',s.note));step.append(node('span','',s.icon),description);children.push(step);});$('workflow').replaceChildren(...children);
  $('workflowNote').textContent=source==='azure'?text('Editör ve bağımsız denetçi Foundry üzerinde çalıştı. Ölçümler kod tarafından hesaplandı.','Editor and independent reviewer ran on Foundry. Measurements were computed in code.'):text('Yerel demo: geometri + kurallar + anlatım şablonları. AI ajanları yalnızca Azure bağlantısıyla çalışır.','Local demo: geometry + rules + narrative templates. AI agents run only when Azure is connected.');
}
function renderEvidence(){
  const a=state.match.analysis;
  $('verdict').textContent=a.verdict[state.lang];$('caveat').textContent=a.caveat[state.lang];
  $('evidenceList').replaceChildren(...a.facts.map(f=>{const b=node('button','evidence-item');b.dataset.fact=f.id;b.title=f.detail[state.lang];const body=node('div');body.append(node('strong','',f.label[state.lang]),node('small','',`${sec(f.t)} — ${sec(f.end)}`));b.append(node('span','fact-number',f.id),body,node('span','fact-arrow','↗'));b.onclick=()=>jumpFact(f.id);return b;}));
  $('metrics').replaceChildren(...a.metrics.map(m=>{const card=node('article','metric');const value=node('div','metric-value');if(m.before!==undefined)value.append(node('span','metric-before',`${m.before} →`));value.append(node('span',m.before!==undefined?'metric-after':'',String(m.value)),node('small','',m.unit));card.append(node('div','metric-label',m.label[state.lang]),value,node('div','metric-note',text('Hesaplanan · 00:00–00:08 penceresi','Computed · 00:00–00:08 window')));return card;}));
  const headlines={decoy:['Asisti görüyorsun.\nAlanı açanı da gör.','You see the assist.\nNow see who made space.'],'third-man':['İlk pası izle.\nÜçüncü adamı bul.','Follow the first pass.\nFind the third man.'],press:['Top kaybolmadan,\nseçenekler kayboldu.','Before the ball was lost,\nthe options were gone.']};
  $('insightHeadline').textContent=headlines[state.match.id][state.lang==='tr'?0:1];$('insightHeadline').style.whiteSpace='pre-line';
}
function jumpFact(id){const f=state.match.analysis.facts.find(f=>f.id===id);if(!f)return;stop();state.time=f.t;state.selected=id;renderFrame();document.querySelectorAll('[data-fact]').forEach(b=>b.classList.toggle('active',b.dataset.fact===id));}
function buildPlayers(){
  $('playerLayer').replaceChildren(...state.match.players.map(p=>{const g=svg('g',{'data-player':p.id,class:'player',tabindex:0,role:'button','aria-label':`${p.number} · ${p.name}`});g.append(svg('circle',{r:1.65,fill:p.team==='home'?'#c5f665':'#ed9e83',stroke:'#142318','stroke-width':.38}),svg('text',{class:'player-number',fill:'#1a2914'},p.number));
    if(p.id===state.match.scenario.focus){g.append(svg('circle',{r:2.6,class:'player-focus'}),svg('text',{class:'player-name',y:-3.5},p.name.toUpperCase()));g.classList.add('selected');}
    g.onclick=()=>toast(`${p.name} · #${p.number} · ${p.team==='home'?'Northstar FC':'Ember Athletic'}`);g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();g.onclick();}};return g;}));
}
function currentFrame(){return state.match.frames[Math.min(Math.round(state.time*10),state.match.frames.length-1)];}
function renderOverlays(frame){
  const layer=$('overlayLayer'),trails=$('trailLayer');layer.replaceChildren();trails.replaceChildren();
  if(!state.overlays)return;
  const a=state.match.analysis,s=state.match.scenario;
  const pos=id=>frame.players.find(p=>p.id===id);
  const before=state.match.frames[0];
  for(const o of a.overlays){
    if(o.type==='space'){if(state.time>=4)layer.append(svg('ellipse',{cx:o.x,cy:o.y,rx:o.rx,ry:o.ry,fill:'url(#spaceGlow)',stroke:'#c5f665','stroke-width':.15,'stroke-dasharray':'.6 .7',opacity:.8}));}
    if(o.type==='lane'&&state.time>=5){layer.append(svg('path',{d:`M${o.from.x},${o.from.y} L${o.to.x},${o.to.y}`,stroke:'#c5f665','stroke-width':1.2,opacity:.08}),svg('path',{d:`M${o.from.x},${o.from.y} L${o.to.x},${o.to.y}`,stroke:'#c5f665','stroke-width':.3,'stroke-dasharray':'1 1','marker-end':'url(#arrow)'}));}
    if(o.type==='run'||o.type==='defender'){
      const start=before.players.find(p=>p.id===o.player),p=pos(o.player),end=state.match.frames[Math.round(s.keyTime*10)].players.find(p=>p.id===o.player);
      const color=o.type==='defender'?'#ed9e83':'#c5f665';
      layer.append(svg('path',{d:`M${start.x},${start.y} Q${(start.x+end.x)/2},${start.y} ${end.x},${end.y}`,stroke:color,'stroke-width':.28,fill:'none','stroke-dasharray':'.7 1',opacity:.45,'marker-end':o.type==='defender'?'url(#coralArrow)':'url(#arrow)'}));
      if(state.time>0.4){const past=state.match.frames.filter(f=>f.t<=state.time&&f.t>=Math.max(0,state.time-5)&&Math.round(f.t*10)%3===0).map(f=>f.players.find(v=>v.id===o.player));if(past.length)trails.append(svg('polyline',{points:past.map(v=>`${v.x},${v.y}`).join(' '),stroke:color,'stroke-width':.5,opacity:.55,fill:'none','stroke-linecap':'round'}));}
    }
    if(o.type==='pressure'&&state.time>=3){const p=pos(o.player),target=pos(o.to);layer.append(svg('path',{d:`M${p.x},${p.y} L${target.x},${target.y}`,stroke:'#c5f665','stroke-width':.3,'stroke-dasharray':'.6 .7',opacity:.7}));}
  }
}
function renderFrame(){
  if(!state.match)return;
  const frame=currentFrame(),s=state.match.scenario;
  frame.players.forEach(p=>{const el=$('playerLayer').querySelector(`[data-player="${p.id}"]`);el?.setAttribute('transform',`translate(${p.x} ${p.y})`);});
  $('ball').setAttribute('cx',frame.ball.x);$('ball').setAttribute('cy',frame.ball.y);$('ballShadow').setAttribute('cx',frame.ball.x+.2);$('ballShadow').setAttribute('cy',frame.ball.y+.3);
  renderOverlays(frame);
  $('scrubber').value=String(state.time);$('scrubber').style.background=`linear-gradient(to right, #c5f665 ${state.time/s.duration*100}%, #3c4832 ${state.time/s.duration*100}%)`;
  $('timeCounter').replaceChildren(document.createTextNode(sec(state.time)+' '),node('i','',`/ ${sec(s.duration)}`));
  const [m,ss]=s.minute.split(':').map(Number);$('matchTime').textContent=sec(m*60+ss+state.time);
  $('homeScore').textContent=state.match.id!=='press'&&state.time>=12.3?'2':'1';
  const annotations={decoy:[text('Koşuyu takip et.','Follow the run.'),text('Stoper dışarı kayıyor.','The centre-back shifts.'),text('İç koridor açıldı.','The inside lane opens.')],'third-man':[text('Bağlantı pası hazırlanıyor.','The link pass takes shape.'),text('Üçüncü adam hareketleniyor.','The third man is moving.'),text('Deniz boşlukta topla buluşuyor.','Deniz receives in space.')],press:[text('Pas kenara gidiyor.','The pass goes wide.'),text('Baskı çemberi daralıyor.','The pressure closes in.'),text('Top kazanımı doğrulandı.','Turnover confirmed.')]};
  const annotation=annotations[state.match.id][state.time<3?0:state.time<8?1:2];const p=state.match.analysis.focus;
  $('annotationText').replaceChildren(document.createTextNode(annotation),node('small','',`${p.number} · ${p.name.toUpperCase()}`));
  $('pitchAnnotation').hidden=!state.overlays;
}
async function load(id){
  stop();const loading=++state.loading;
  $('sceneTitle').textContent=text('Yükleniyor…','Loading…');
  try{const match=await api(`/api/match/${id}?seed=${state.seed}`);if(loading!==state.loading)return;state.match=match;state.time=0;state.selected=null;$('answer').textContent=dictionary[state.lang].askHint;$('question').value='';$('sceneTitle').textContent=match.scenario.title[state.lang];$('pattern').textContent=match.scenario.pattern[state.lang];$('sequenceLabel').textContent=`${text('SEKANS','SEQUENCE')} ${String(state.scenarios.findIndex(s=>s.id===id)+1).padStart(2,'0')} / 03`;$('scrubber').max=match.scenario.duration;labels();buildPlayers();renderEvidence();renderFrame();$('timelineMarkers').replaceChildren(...match.events.map(e=>{const n=node('i');n.style.left=`${e.t/match.scenario.duration*100}%`;return n;}));void updateNarrative();}
  catch{toast(text('Pozisyon yüklenemedi. Sunucuyu kontrol et.','Could not load the sequence. Check the server.'));}
}
$('play').onclick=()=>{if(!state.match)return;if(state.playing){stop();return;}if(state.time>=state.match.scenario.duration)state.time=0;state.playing=true;$('play').textContent='Ⅱ';$('play').setAttribute('aria-label',text('Duraklat','Pause'));};
$('restart').onclick=()=>{stop();state.time=0;renderFrame();};
$('scrubber').oninput=e=>{stop();state.time=Number(e.target.value);state.selected=null;document.querySelectorAll('[data-fact]').forEach(b=>b.classList.remove('active'));renderFrame();};
$('speed').onclick=()=>{state.speed=state.speed===1?.5:state.speed===.5?2:1;$('speed').textContent=state.speed+'×';};
$('overlays').onchange=e=>{state.overlays=e.target.checked;renderFrame();};
$('keyMoment').onclick=()=>{stop();state.time=state.match.scenario.keyTime;renderFrame();};
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{state.mode=b.dataset.mode;labels();void updateNarrative();});
$('language').onclick=()=>{state.lang=state.lang==='tr'?'en':'tr';labels();if(state.match){$('sceneTitle').textContent=state.match.scenario.title[state.lang];$('pattern').textContent=state.match.scenario.pattern[state.lang];renderEvidence();renderFrame();$('answer').textContent=dictionary[state.lang].askHint;void updateNarrative();}};
const exportData=()=>{if(!state.match)return;const{analysis,...data}=state.match;download(data,`ghost-play-${data.id}-${data.seed}.json`);toast(text('Sentetik veri indirildi.','Synthetic data downloaded.'));};
$('export').onclick=exportData;$('dataNav').onclick=exportData;$('studioNav').onclick=()=>window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
$('askForm').onsubmit=async e=>{e.preventDefault();if(!state.match)return;const question=$('question').value.trim();if(!question)return;const snapshot={id:state.match.id,seed:state.seed,lang:state.lang,mode:state.mode,question};$('askButton').disabled=true;$('answer').textContent=text('Kanıtlar kontrol ediliyor…','Checking the evidence…');try{const result=await api('/api/ask',snapshot);if(state.match.id===snapshot.id&&state.lang===snapshot.lang){$('answer').textContent=result.text;if(result.warning)toast(result.warning);}}catch{$('answer').textContent=text('Yanıt alınamadı. Tekrar dene.','Could not get an answer. Try again.');}finally{$('askButton').disabled=false;}};
$('recap').onclick=async()=>{if(!state.match)return;stop();$('recap').disabled=true;const snapshot={id:state.match.id,seed:state.seed,mode:state.mode,lang:state.lang};try{const recap=await api('/api/recap',snapshot);state.recap=recap;$('recapTitle').textContent=recap.title;$('recapText').textContent=recap.text;$('recapCaveat').textContent=recap.caveat;$('recapEvidence').replaceChildren(...recap.evidence.map(f=>{const p=node('div');p.append(node('b','',`${f.id} · ${sec(f.from)}`),document.createTextNode(f.text));return p;}));$('recapDialog').showModal();}catch{toast(text('Özet oluşturulamadı.','Could not create the recap.'));}finally{$('recap').disabled=false;}};
$('closeRecap').onclick=()=>$('recapDialog').close();
$('downloadRecap').onclick=()=>{if(state.recap)download(state.recap,'ghost-play-recap.json');};
$('copyRecap').onclick=async()=>{try{await navigator.clipboard.writeText(state.recap.text);toast(text('Özet kopyalandı.','Recap copied.'));}catch{toast(text('Kopyalanamadı. JSON olarak indirebilirsin.','Copy unavailable. Download the JSON instead.'));}};
let previous=performance.now();
function animate(now){const dt=Math.min((now-previous)/1000,.1);previous=now;if(state.playing&&state.match){state.time=Math.min(state.time+dt*state.speed,state.match.scenario.duration);renderFrame();if(state.time>=state.match.scenario.duration)stop();}requestAnimationFrame(animate);}
requestAnimationFrame(animate);
try{[state.scenarios,state.health]=await Promise.all([api('/api/scenarios'),api('/api/health')]);await load('decoy');}catch{$('narrative').textContent='Sunucuya bağlanılamadı. Sayfayı yenileyip tekrar dene. / Server unavailable. Reload to try again.';toast('Sunucu bağlantısı kurulamadı. / Server unavailable.');}
