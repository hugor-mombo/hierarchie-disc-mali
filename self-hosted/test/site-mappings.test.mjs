import {test} from 'node:test';
import assert from 'node:assert/strict';
import {demoState} from '../lib/demo.mjs';
import {SITE_MAPPING_HEADERS,dhisSiteCounts,siteMappingReport,siteMappingCSV} from '../lib/site-mappings.mjs';
import {parseMappings} from '../lib/reconcile.mjs';
import {DISTRICT_GROUP,ASC_GROUP,relevantDhis} from '../lib/scope.mjs';
import {automaticMappings} from '../lib/auto-match.mjs';
import {planSync} from '../lib/sync-plan.mjs';
test('niveau 3 limité au groupe District sanitaire, sans modifier les données complètes',()=>{
 const s=demoState();s.snapshot.dhis.push({id:'excluded',name:'Autre district',level:3,parent:'h1',groups:[]});
 assert.equal(relevantDhis({level:3,groups:[DISTRICT_GROUP]}),true);assert.equal(relevantDhis({level:3,groups:[]}),false);assert.equal(relevantDhis({level:3}),false);assert.equal(relevantDhis({level:2}),true);
 assert.ok(s.snapshot.dhis.some(n=>n.id==='excluded'));assert.ok(!automaticMappings(s.snapshot,[],s.levels).some(m=>m.dhisId==='excluded'));
 s.snapshot.dhis.find(n=>n.id==='h2').groups=[];assert.throws(()=>planSync(s.snapshot,s.mappings,s.levels,{originSource:'dhis',originId:'h2',operation:'rename'}),/groupe/);
});
test('CSV ASC conserve les trois colonnes, les UID et les correspondances enregistrées seulement',()=>{
 const s=demoState(),report=siteMappingReport(s.snapshot,s.mappings),text=siteMappingCSV(s.snapshot,s.mappings);
 assert.equal(report.rows.length,3);assert.equal(report.discCount,7);assert.equal(report.dhisCount,7);assert.equal(report.discUnlinked,4);assert.equal(report.dhisUnlinked,4);
 assert.ok(text.startsWith('\ufeff"chw_site_id","dhis2_org_unit","active",'));assert.ok(text.includes('"region_disc"'));assert.ok(text.includes('"district_dhis2"'));assert.deepEqual(parseMappings(text),s.mappings.filter(m=>['d5','d6','d7'].includes(m.discId)));
 assert.ok(!parseMappings(text).some(m=>['d8','d3'].includes(m.discId)));assert.ok(!parseMappings(text).some(m=>m.dhisId==='h8'));
});
test('liens absents, mauvais niveau et UO hors groupe ne sont pas exportés',()=>{
 const s=demoState();s.snapshot.dhis.find(n=>n.id==='h6').groups=[];s.snapshot.dhis.find(n=>n.id==='h7').level=5;s.snapshot.dhis=s.snapshot.dhis.filter(n=>n.id!=='h5');
 const r=siteMappingReport(s.snapshot,s.mappings);assert.equal(r.rows.length,0);assert.equal(r.excluded.length,3);
 assert.throws(()=>siteMappingReport(s.snapshot,[...s.mappings,s.mappings[0]]),/dupliquée/);
});
test('fichier mis à jour après un rapprochement, sites fermés exclus',()=>{
 const s=demoState();s.snapshot.dhis.find(n=>n.id==='h6').closedDate='2020-01-01';
 const before=siteMappingReport(s.snapshot,s.mappings).rows.length;s.mappings.push({discId:'d8',dhisId:'h8'});
 assert.equal(siteMappingReport(s.snapshot,s.mappings).rows.length,before+1);assert.ok(!siteMappingCSV(s.snapshot,s.mappings).includes('"d6","h6","true"'));assert.equal(siteMappingReport(s.snapshot,s.mappings).dhisSites.closed,1);
});
test('un relevé ancien sans groupes exige une actualisation avant export ASC',()=>{
 const s=demoState();delete s.snapshot.dhis.find(n=>n.id==='h5').groups;assert.throws(()=>siteMappingCSV(s.snapshot,s.mappings),/Actualiser/);
});
test('arborescences DISC et DHIS2 exportées séparément avec leurs niveaux et identifiants',()=>{
 const s=demoState(),report=siteMappingReport(s.snapshot,s.mappings),r=report.rows.find(r=>r.discId==='d5');
 assert.deepEqual(r.discBranch,{region:'Koulikoro',regionId:'d1',district:'Kati',districtId:'d2',cscom:'CSCOM de Kalabancoro',cscomId:'d3',intermediate:'Zone Kalabancoro',intermediateId:'d4'});
 assert.equal(r.dhisBranch.regionId,'h1');assert.equal(r.dhisBranch.districtId,'h2');assert.equal(r.dhisBranch.cscomId,'h4');assert.equal(r.dhisBranch.intermediateId,'h3');
 const lines=siteMappingCSV(s.snapshot,s.mappings).replace(/^\ufeff/,'').split('\r\n'),cells=lines[1].split(',').map(s=>s.slice(1,-1)),row=Object.fromEntries(SITE_MAPPING_HEADERS.map((h,i)=>[h,cells[i]]));
 assert.equal(cells.length,SITE_MAPPING_HEADERS.length);assert.equal(row.region_disc,'Koulikoro');assert.equal(row.district_dhis2,'District de Kati');assert.equal(row.zone_supervision_disc,'Zone Kalabancoro');assert.equal(row.aire_sante_dhis2,'Aire de Kalabancoro');assert.ok(row.chemin_disc.includes('Mali /'));assert.equal(row.statut_dhis2,'Ouvert');
});
test('compteurs ouverts fermés inconnus sur tous les ASC DHIS2, exclusion dès la date effective',()=>{
 const s=demoState(),h=id=>s.snapshot.dhis.find(n=>n.id===id),today='2026-10-21';
 h('h5').closedDate='2026-10-20';h('h6').closedDate='2026-10-21T00:00:00.000';h('h7').closedDate='2026-10-22';h('h8').closedDate='2026-02-30';delete h('h9').closedDate;
 s.snapshot.dhis.push({id:'maternity',level:6,groups:[],closedDate:null},{id:'not-site',level:5,groups:[ASC_GROUP],closedDate:null});
 assert.deepEqual(dhisSiteCounts(s.snapshot,today),{total:7,open:3,closed:2,unknown:2,scheduled:1});
 s.mappings.push({discId:'d8',dhisId:'h8'});const r=siteMappingReport(s.snapshot,s.mappings,today);assert.deepEqual(r.rows.map(r=>r.dhisId),['h7']);assert.equal(r.dhisOpenUnlinked,2);assert.equal(r.excluded.filter(r=>r.category==='closed').length,2);assert.equal(r.excluded.filter(r=>r.category==='unknown').length,1);
 assert.ok(siteMappingCSV(s.snapshot,s.mappings,today).includes('2026-10-22'));assert.equal(siteMappingReport(s.snapshot,s.mappings,'2026-10-22').rows.length,0);
});
