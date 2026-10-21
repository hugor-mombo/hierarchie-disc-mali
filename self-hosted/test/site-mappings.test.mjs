import {test} from 'node:test';
import assert from 'node:assert/strict';
import {demoState} from '../lib/demo.mjs';
import {siteMappingReport,siteMappingCSV} from '../lib/site-mappings.mjs';
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
 assert.equal(text.split('\r\n')[0],'\ufeff"chw_site_id","dhis2_org_unit","active"');assert.deepEqual(parseMappings(text),s.mappings.filter(m=>['d5','d6','d7'].includes(m.discId)));
 assert.ok(!text.includes('d8'));assert.ok(!text.includes('h8'));assert.ok(!text.includes('d3'));
});
test('liens absents, mauvais niveau et UO hors groupe ne sont pas exportés',()=>{
 const s=demoState();s.snapshot.dhis.find(n=>n.id==='h6').groups=[];s.snapshot.dhis.find(n=>n.id==='h7').level=5;s.snapshot.dhis=s.snapshot.dhis.filter(n=>n.id!=='h5');
 const r=siteMappingReport(s.snapshot,s.mappings);assert.equal(r.rows.length,0);assert.equal(r.excluded.length,3);
 assert.throws(()=>siteMappingReport(s.snapshot,[...s.mappings,s.mappings[0]]),/dupliquée/);
});
test('fichier mis à jour après un rapprochement, sans confondre fermeture et activation du lien',()=>{
 const s=demoState();s.snapshot.dhis.find(n=>n.id==='h6').closedDate='2020-01-01';
 const before=siteMappingReport(s.snapshot,s.mappings).rows.length;s.mappings.push({discId:'d8',dhisId:'h8'});
 assert.equal(siteMappingReport(s.snapshot,s.mappings).rows.length,before+1);assert.ok(siteMappingCSV(s.snapshot,s.mappings).includes('"d6","h6","true"'));
});
test('un relevé ancien sans groupes exige une actualisation avant export ASC',()=>{
 const s=demoState();delete s.snapshot.dhis.find(n=>n.id==='h5').groups;assert.throws(()=>siteMappingCSV(s.snapshot,s.mappings),/Actualiser/);
});
