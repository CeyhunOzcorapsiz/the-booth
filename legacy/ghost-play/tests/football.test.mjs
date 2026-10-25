import test from 'node:test';
import assert from 'node:assert/strict';
import { generateMatch, analyze, narrative, segmentDistance, distance, SCENARIOS } from '../lib/football.mjs';
import { makeServer, callFoundry } from '../server.mjs';

test('synthetic tracking is reproducible and changes with the seed',()=>{
  assert.deepEqual(generateMatch('decoy',42),generateMatch('decoy',42));
  assert.notDeepEqual(generateMatch('decoy',42).frames,generateMatch('decoy',43).frames);
});
test('all scenarios have continuous, bounded tracking for 22 players and the ball',()=>{
  for(const s of SCENARIOS){const m=generateMatch(s.id);
    assert.equal(m.synthetic,true);assert.equal(m.frames.length,161);
    for(let i=0;i<m.frames.length;i++){
      const f=m.frames[i];assert.equal(f.players.length,22);assert.equal(new Set(f.players.map(p=>p.id)).size,22);
      for(const p of [...f.players,f.ball]){assert.ok(p.x>=0&&p.x<=105);assert.ok(p.y>=0&&p.y<=68);}
      if(i>0)for(let j=0;j<22;j++)assert.ok(distance(f.players[j],m.frames[i-1].players[j])/.1<12,'Player must not teleport');
    }
    for(const e of m.events){assert.ok(e.t>=0&&e.t<=s.duration);assert.ok(m.players.some(p=>p.id===e.player));}
  }
});
test('segment distance handles endpoints and perpendicular projection',()=>{
  assert.equal(segmentDistance({x:5,y:3},{x:0,y:0},{x:10,y:0}),3);
  assert.equal(segmentDistance({x:13,y:4},{x:0,y:0},{x:10,y:0}),5);
});
test('the detector distinguishes a decoy pattern from stationary or absent evidence',()=>{
  const m=generateMatch('decoy');assert.equal(analyze(m).accepted,true);
  const frozen=structuredClone(m);frozen.frames.forEach(f=>{f.players=structuredClone(m.frames[0].players);});
  assert.equal(analyze(frozen).accepted,false);
  assert.equal(analyze(frozen).metrics[1].value,0);
});
test('third-man and press detectors require the supporting event chain',()=>{
  for(const id of ['third-man','press']){const m=generateMatch(id);assert.equal(analyze(m).accepted,true);m.events=[];assert.equal(analyze(m).accepted,false);}
});
test('metrics respond to changed defender positions instead of hardcoded scenario labels',()=>{
  const m=generateMatch('decoy');const baseline=analyze(m);
  const frame=m.frames[80];const d=frame.players.find(p=>p.id==='A4');d.x=73;d.y=34;
  const changed=analyze(m);assert.equal(changed.metrics[0].value,0);assert.notEqual(changed.metrics[0].value,baseline.metrics[0].value);assert.equal(changed.accepted,false);
});
test('both audiences and languages are supported with valid evidence references',()=>{
  for(const s of SCENARIOS){const m=generateMatch(s.id),a=analyze(m);for(const lang of ['tr','en']){const fan=narrative(m,a,'fan',lang),analyst=narrative(m,a,'analyst',lang);assert.notEqual(fan.text,analyst.text);assert.equal(fan.source,'local');assert.ok(fan.evidenceIds.every(id=>a.facts.some(f=>f.id===id)));}}
});
test('HTTP routes validate input, keep credentials private, and export synthetic data',async()=>{
  const server=makeServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const root=`http://127.0.0.1:${server.address().port}`;
  try{
    const health=await fetch(root+'/api/health').then(r=>r.json());assert.equal(health.ok,true);assert.equal(health.AZURE_AI_API_KEY,undefined);
    const m=await fetch(root+'/api/match/decoy?seed=42').then(r=>r.json());assert.equal(m.analysis.accepted,true);
    assert.equal((await fetch(root+'/api/match/decoy?seed=nope')).status,400);
    assert.equal((await fetch(root+'/api/match/unknown')).status,400);
    assert.equal((await fetch(root+'/.env')).status,404);
    assert.equal((await fetch(root+'/server.mjs')).status,404);
    const exported=await fetch(root+'/api/export/press').then(r=>r.json());assert.equal(exported.synthetic,true);
    const post=(path,body,extra={})=>fetch(root+path,{method:'POST',headers:{'Content-Type':'application/json',...extra},body:JSON.stringify(body)});
    assert.equal((await post('/api/narrative',{id:'decoy',mode:'invalid'})).status,400);
    assert.equal((await post('/api/narrative',{id:'decoy'}, {Origin:'https://attacker.example'})).status,403);
    const recap=await post('/api/recap',{id:'decoy',lang:'en',mode:'analyst'}).then(r=>r.json());assert.equal(recap.synthetic,true);assert.equal(recap.evidence.length,3);
    const unknown=await post('/api/ask',{id:'decoy',question:'Who won the World Cup?'}).then(r=>r.json());assert.equal(unknown.evidenceIds.length,0);
    const causal=await post('/api/ask',{id:'decoy',question:'Bu koşu kesin gol sebebi mi?'}).then(r=>r.json());assert.match(causal.text,/nedensellik/);assert.equal(causal.evidenceIds.length,0);
    const stream=await fetch(root+'/api/stream/decoy');const reader=stream.body.getReader();const first=await reader.read();assert.match(new TextDecoder().decode(first.value),/event: frame/);await reader.cancel();
  } finally {await new Promise(r=>server.close(r));}
});
test('Foundry adapter uses the configured endpoint and never returns credentials',async()=>{
  const keys=['AZURE_AI_ENDPOINT','AZURE_AI_API_KEY','AZURE_AI_MODEL'];const old=Object.fromEntries(keys.map(k=>[k,process.env[k]]));
  Object.assign(process.env,{AZURE_AI_ENDPOINT:'https://example.services.ai.azure.com/models',AZURE_AI_API_KEY:'test-only-key',AZURE_AI_MODEL:'test-model'});
  try{const result=await callFoundry([{role:'user',content:'test'}],async(url,opts)=>{assert.equal(url.pathname,'/models/chat/completions');assert.equal(opts.headers['api-key'],'test-only-key');assert.equal(JSON.parse(opts.body).model,'test-model');return {ok:true,json:async()=>({choices:[{message:{content:'{"text":"verified"}'}}]})};});assert.deepEqual(result,{text:'verified'});
    process.env.AZURE_AI_ENDPOINT='http://localhost:3210';await assert.rejects(callFoundry([]),/HTTPS/);
  } finally {for(const k of keys)if(old[k]===undefined)delete process.env[k];else process.env[k]=old[k];}
});
