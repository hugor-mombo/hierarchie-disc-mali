import {test} from 'node:test';
import assert from 'node:assert/strict';
import {automaticMappings} from '../lib/auto-match.mjs';
import {demoState} from '../lib/demo.mjs';
import {compare,matchingName} from '../lib/reconcile.mjs';
import {ASC_GROUP} from '../lib/scope.mjs';

test('reconnaissance de haut en bas sans validation manuelle, niveaux intermédiaires traversés',()=>{
  const s=demoState(),auto=automaticMappings(s.snapshot,[],s.levels),ids=new Map(auto.map(m=>[m.discId,m.dhisId]));
  for(const [d,h] of [['d0','h0'],['d1','h1'],['d2','h2'],['d3','h4'],['d5','h5'],['d6','h6'],['d8','h8']])assert.equal(ids.get(d),h);
  assert.equal(ids.has('d4'),false);assert.equal(ids.has('d7'),false);assert.equal(ids.has('d9'),false);assert.equal(ids.has('d10'),false);
  assert.equal(compare(s.snapshot,auto,s.levels).find(r=>r.disc?.id==='d5').status,'aligned');
  assert.equal(automaticMappings(s.snapshot,auto,s.levels).length,0);
});
test('même nom dans deux districts : la branche distingue les homonymes',()=>{
  const s=demoState();s.snapshot.disc.push({id:'other-d',name:'District voisin',type:'c30_district',parent:'d1'},{id:'other-a',name:'Autre aire',type:'c40_health_area',parent:'other-d'},{id:'other-z',name:'Autre zone',type:'c50_supervision_area',parent:'other-a'},{id:'other-site',name:'Sébénikoro',type:'c60_chw_site',parent:'other-z'});
  s.snapshot.dhis.push({id:'other-hd',name:'District voisin',level:3,parent:'h1',groups:[]},{id:'other-ha',name:'Autre aire',level:5,parent:'other-hd',groups:['a8PnG1kmKY9']},{id:'other-hs',name:'Sébénikoro',level:6,parent:'other-ha',groups:[ASC_GROUP]});
  const ids=new Map(automaticMappings(s.snapshot,[],s.levels).map(m=>[m.discId,m.dhisId]));assert.equal(ids.get('d6'),'h6');assert.equal(ids.get('other-site'),'other-hs');
});
test('doublons dans une branche et incertitude réciproque restent à examiner',()=>{
  const s=demoState();s.snapshot.disc.push({...s.snapshot.disc.find(n=>n.id==='d6'),id:'duplicate'});
  let ids=new Map(automaticMappings(s.snapshot,[],s.levels).map(m=>[m.discId,m.dhisId]));assert.equal(ids.has('d6'),false);assert.equal(ids.has('duplicate'),false);
  s.snapshot.disc.pop();s.snapshot.dhis.push({...s.snapshot.dhis.find(n=>n.id==='h6'),id:'duplicate-h'});
  ids=new Map(automaticMappings(s.snapshot,[],s.levels).map(m=>[m.discId,m.dhisId]));assert.equal(ids.has('d6'),false);
});
test('absence d’un parent reconnu, mauvais parent ou niveaux hors périmètre refusés',()=>{
  const s=demoState();s.snapshot.disc.find(n=>n.id==='d3').name='Aire différente';
  const ids=new Map(automaticMappings(s.snapshot,[],s.levels).map(m=>[m.discId,m.dhisId]));assert.equal(ids.has('d6'),false);assert.equal(ids.has('d7'),false);
  s.snapshot.disc.find(n=>n.id==='d3').name='CSCOM Kalabancoro';s.snapshot.dhis.find(n=>n.id==='h6').groups=[];
  assert.ok(!automaticMappings(s.snapshot,[],s.levels).some(m=>m.discId==='d6'));
});
test('identifiant embarqué unique avec branche valide peut reconnaître un nom différent',()=>{
  const s=demoState();s.snapshot.disc.find(n=>n.id==='d10').dhisId='h11';
  const auto=automaticMappings(s.snapshot,[],s.levels),m=auto.find(m=>m.discId==='d10');assert.equal(m.dhisId,'h11');assert.equal(m.matchBasis,'embedded-id');
  assert.equal(compare(s.snapshot,auto,s.levels).find(r=>r.disc?.id==='d10').status,'name');
  s.snapshot.disc.find(n=>n.id==='d11').dhisId='h11';assert.ok(!automaticMappings(s.snapshot,[],s.levels).some(m=>m.dhisId==='h11'));
});
test('les décisions manuelles et les exclusions sont prioritaires',()=>{
  const s=demoState(),manual=[{discId:'d6',dhisId:'h11'}];
  assert.ok(!automaticMappings(s.snapshot,manual,s.levels).some(m=>m.discId==='d6'||m.dhisId==='h11'));
  assert.ok(!automaticMappings(s.snapshot,[],s.levels,['d6']).some(m=>m.discId==='d6'));
  s.snapshot.disc.push({...s.snapshot.disc.find(n=>n.id==='d6'),id:'duplicate'});
  assert.ok(!automaticMappings(s.snapshot,[],s.levels,['d6']).some(m=>m.discId==='duplicate'));
});
test('pas de rapprochement automatique sur un cycle ou un parent absent',()=>{
  const s=demoState();s.snapshot.disc.find(n=>n.id==='d4').parent='absent';
  assert.ok(!automaticMappings(s.snapshot,[],s.levels).some(m=>['d5','d6'].includes(m.discId)));
  s.snapshot.disc.find(n=>n.id==='d4').parent='d6';assert.ok(!automaticMappings(s.snapshot,[],s.levels).some(m=>m.discId==='d6'));
});
test('casse accents préfixes et apostrophes concordent ; les numéros restent distincts',()=>{
  assert.equal(matchingName('Site ASC de N’Golobougou'),matchingName('NGOLOBOUGOU'));
  assert.equal(matchingName('CSCOM de Sébénikoro'),matchingName('SEBENIKORO'));
  assert.notEqual(matchingName('Site 1'),matchingName('Site 2'));
});
