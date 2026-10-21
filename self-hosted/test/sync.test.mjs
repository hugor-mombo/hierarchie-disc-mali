import {test} from 'node:test';
import assert from 'node:assert/strict';
import {demoState} from '../lib/demo.mjs';
import {CSCOM_GROUP,ASC_GROUP,relevantDhis,siteStatus} from '../lib/scope.mjs';
import {compare} from '../lib/reconcile.mjs';
import {fetchDHIS} from '../lib/sources.mjs';
import {planSync,parentCandidates,targetType,assertSamePlan} from '../lib/sync-plan.mjs';

test('périmètre CSCOM et Sites ASC sans maternités ni niveau 4, relevé complet conservé',()=>{
  const s=demoState();s.snapshot.dhis.push({id:'m',name:'Maternité rurale',level:6,parent:'h4',groups:[]},{id:'f',name:'Autre formation',level:5,parent:'h3',groups:[]});
  const size=s.snapshot.dhis.length,rows=compare(s.snapshot,s.mappings,s.levels,relevantDhis);
  assert.equal(relevantDhis(s.snapshot.dhis.find(n=>n.id==='h3')),false);
  assert.ok(!rows.some(r=>r.dhis?.id==='m'||r.dhis?.id==='f'));
  assert.equal(s.snapshot.dhis.length,size);
  assert.equal(relevantDhis({level:5,groups:[CSCOM_GROUP]}),true);
  assert.equal(relevantDhis({level:6,groups:[ASC_GROUP]}),true);
  assert.equal(relevantDhis({level:6}),false);
});
test('fermeture passée, future et statut absent ne sont pas confondus',()=>{
  assert.match(siteStatus({level:6,closedDate:'2026-10-20T00:00:00'},'2026-10-21'),/^Fermé/);
  assert.match(siteStatus({level:6,closedDate:'2026-10-22'},'2026-10-21'),/^Fermeture prévue/);
  assert.equal(siteStatus({level:6,closedDate:null}),'Ouvert');assert.equal(siteStatus({level:6}),'Statut non relevé');
});
test('DHIS collecte les groupes API29 et conserve toutes les UO avec les dates',async()=>{
  const urls=[];
  const result=await fetchDHIS({DHIS_USER:'u',DHIS_PASSWORD:'p'},async url=>{
    urls.push(url);let data;
    if(url.includes('organisationUnitLevels'))data={organisationUnitLevels:[]};
    else if(url.includes('organisationUnitGroups')){const group=url.includes(CSCOM_GROUP)?CSCOM_GROUP:ASC_GROUP;data={id:group,organisationUnits:[{id:group===CSCOM_GROUP?'cscom':'asc'}]};}
    else data={pager:{pageCount:1},organisationUnits:[{id:'cscom',name:'CSCOM',level:5},{id:'asc',name:'ASC fermé',level:6,closedDate:'2025-01-01'},{id:'m',name:'Maternité',level:6}]};
    return {ok:true,json:async()=>data};
  });
  assert.equal(result.nodes.length,3);assert.deepEqual(result.nodes[0].groups,[CSCOM_GROUP]);assert.deepEqual(result.nodes[1].groups,[ASC_GROUP]);assert.equal(result.nodes[1].closedDate,'2025-01-01');
  assert.ok(urls.some(u=>u.includes('/api/29/organisationUnitGroups/')));
  await assert.rejects(fetchDHIS({DHIS_USER:'u',DHIS_PASSWORD:'p'},async()=>({ok:true,json:async()=>({})})),/Groupe DHIS2 incomplet/);
});
test('DHIS est la référence par défaut, création DISC sous la supervision correspondante',()=>{
  const s=demoState(),origin=s.snapshot.dhis.find(n=>n.id==='h11');
  const candidates=parentCandidates(s.snapshot,s.mappings,'dhis',origin,targetType(origin,'dhis',s.levels),s.levels);
  assert.deepEqual(candidates.map(n=>n.id),['d4']);
  const p=planSync(s.snapshot,s.mappings,s.levels,{originId:'h11',operation:'create',parentId:'d4'});
  assert.equal(p.originSource,'dhis');assert.equal(p.targetSource,'disc');assert.equal(p.type,'c60_chw_site');assert.equal(p.parent.id,'d4');
  assert.throws(()=>planSync(s.snapshot,s.mappings,s.levels,{originId:'h11',operation:'create',parentId:'d2'}),/parent compatible/);
});
test('DISC en avance peut créer un Site ASC sur DHIS2 sous le CSCOM rapproché',()=>{
  const s=demoState();const p=planSync(s.snapshot,s.mappings,s.levels,{originSource:'disc',originId:'d10',operation:'create',parentId:'h4'});
  assert.equal(p.targetSource,'dhis');assert.equal(p.parent.id,'h4');
  assert.throws(()=>planSync(s.snapshot,s.mappings,s.levels,{originSource:'disc',originId:'d10',operation:'create',parentId:'h3'}),/parent compatible/);
});
test('renommage et déplacement suivent la référence explicite et un mapping validé',()=>{
  const s=demoState();let p=planSync(s.snapshot,s.mappings,s.levels,{originSource:'dhis',originId:'h5',operation:'rename'});assert.equal(p.target.id,'d5');assert.equal(p.origin.name,'NGOLOBOUGOU');
  p=planSync(s.snapshot,s.mappings,s.levels,{originSource:'disc',originId:'d7',operation:'move',parentId:'h4'});assert.equal(p.target.id,'h7');assert.equal(p.targetSource,'dhis');
  assert.throws(()=>planSync(s.snapshot,s.mappings,s.levels,{originId:'h11',operation:'rename'}),/Valider la correspondance/);
});
test('créations en doublon, hors groupe et branches non rapprochées refusées',()=>{
  const s=demoState();assert.throws(()=>planSync(s.snapshot,s.mappings,s.levels,{originId:'h5',operation:'create',parentId:'d4'}),/correspondance existe/);
  s.snapshot.dhis.push({id:'new',name:'Site ASC de Samaya',level:6,parent:'h4',groups:[ASC_GROUP]});
  assert.throws(()=>planSync(s.snapshot,s.mappings,s.levels,{originId:'new',operation:'create',parentId:'d4'}),/similaire/);
  s.snapshot.dhis.at(-1).groups=[];assert.throws(()=>planSync(s.snapshot,s.mappings,s.levels,{originId:'new',operation:'create',parentId:'d4'}),/groupe/);
  assert.throws(()=>planSync(s.snapshot,[],s.levels,{originId:'h11',operation:'create',parentId:'d4'}),/parent compatible/);
});
test('un plan reste comparable après réordonnancement JSONB mais refuse un changement réel',()=>{
  const s=demoState(),p=planSync(s.snapshot,s.mappings,s.levels,{originId:'h5',operation:'rename'});
  const reordered=Object.fromEntries(Object.entries(p).reverse());assert.doesNotThrow(()=>assertSamePlan(p,reordered));
  assert.throws(()=>assertSamePlan(p,{...p,parent:{id:'changed'}}),/changé/);
});
