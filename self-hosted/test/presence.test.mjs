import {test} from 'node:test';
import assert from 'node:assert/strict';
import {compare} from '../lib/reconcile.mjs';
const levels={c10_central:1,c30_district:3,c40_health_area:5,c60_chw_site:6};
function fixture(){return {disc:[{id:'d',name:'District',type:'c30_district',parent:null},{id:'a',name:'CSCOM Faragouaran',type:'c40_health_area',parent:'d'},{id:'s',name:'Site Nianéguela',type:'c60_chw_site',parent:'a'}],dhis:[{id:'h',name:'District',level:3,parent:null},{id:'b',name:'CSCom Farangouaran',level:5,parent:'h'},{id:'t',name:'Site Nianéguela',level:6,parent:'b'}]};}
test('un site identique avec parent non rapproché reste candidat et jamais absence probable',()=>{
 const rows=compare(fixture(),[{discId:'d',dhisId:'h'}],levels),site=rows.find(r=>r.id==='dhis:t');
 assert.equal(site.presence,'review');assert.equal(site.discCandidates[0].id,'s');assert.equal(rows.find(r=>r.id==='s').presence,'review');
});
test('absence probable seulement sans candidat avec parent rapproché, dans les deux sens',()=>{
 const s=fixture();s.disc=s.disc.filter(n=>n.id!=='s');
 let rows=compare(s,[{discId:'d',dhisId:'h'},{discId:'a',dhisId:'b'}],levels);assert.equal(rows.find(r=>r.id==='dhis:t').presence,'probable');
 rows=compare(s,[{discId:'d',dhisId:'h'}],levels);assert.equal(rows.find(r=>r.id==='dhis:t').presence,'unverified');
 const other=fixture();other.dhis=other.dhis.filter(n=>n.id!=='t');rows=compare(other,[{discId:'d',dhisId:'h'},{discId:'a',dhisId:'b'}],levels);assert.equal(rows.find(r=>r.id==='s').presence,'probable');
});
test('un candidat déjà lié reste signalé, et rapproché ne signifie pas concordant',()=>{
 const s=fixture();s.dhis.push({...s.dhis[2],id:'duplicate'});
 const rows=compare(s,[{discId:'d',dhisId:'h'},{discId:'a',dhisId:'b'},{discId:'s',dhisId:'t'}],levels);
 assert.equal(rows.find(r=>r.id==='a').presence,'linked');assert.equal(rows.find(r=>r.id==='a').status,'name');assert.equal(rows.find(r=>r.id==='dhis:duplicate').presence,'review');assert.equal(rows.find(r=>r.id==='dhis:duplicate').discCandidates[0].linked,true);
});
test('un mapping parent vers une fiche absente ne permet pas de conclure à une absence probable',()=>{
 const s=fixture();s.disc=s.disc.filter(n=>n.id!=='s');
 const rows=compare(s,[{discId:'d',dhisId:'h'},{discId:'deleted',dhisId:'b'}],levels);
 assert.equal(rows.find(r=>r.id==='dhis:t').presence,'unverified');
});
