import {test} from 'node:test';
import assert from 'node:assert/strict';
import {planDeletion,deletionDocSummary,assertDeletionConfirmation} from '../lib/deletion-plan.mjs';
const snapshot={disc:[{id:'r',name:'Central',type:'c10_central',parent:null},{id:'d',name:'District',type:'c30_district',parent:'r'},{id:'s',name:'Site',type:'c60_chw_site',parent:'d'},{id:'other',name:'Autre',type:'c30_district',parent:'r'}],dhis:[{id:'h'}]};
test('périmètre récursif, racine protégée, descendants rapprochés ou identifiant DHIS2 bloquants',()=>{
 assert.deepEqual(planDeletion(snapshot,[],'d').units.map(n=>n.id),['d','s']);assert.throws(()=>planDeletion(snapshot,[],'r'),/racine/);assert.throws(()=>planDeletion(snapshot,[{discId:'s',dhisId:'h'}],'d'),/correspondance/);
 const s=structuredClone(snapshot);s.disc[2].dhisId='h';assert.throws(()=>planDeletion(s,[],'d'),/correspondance/);s.disc[1].parent='absent';assert.throws(()=>planDeletion(s,[],'d'),/incomplète/);
});
test('confirmation doit porter sur le hash, nom, données et sauvegarde du plan courant',()=>{
 const row={unit_name:'Site',status:'prepared',prepared_plan:{hash:'abc',preparedAt:new Date().toISOString()}},b={planHash:'abc',confirmName:'Site',confirmed:true,dataConfirmed:true,backupConfirmed:true};
 assert.doesNotThrow(()=>assertDeletionConfirmation(row,b,true));
 for(const [key,value] of [['planHash','other'],['confirmName','site'],['dataConfirmed',false],['backupConfirmed',false],['confirmed',false]])assert.throws(()=>assertDeletionConfirmation(row,{...b,[key]:value},true),/Confirmer/);
 assert.throws(()=>assertDeletionConfirmation(row,b,false),/désactivées/);assert.throws(()=>assertDeletionConfirmation({...row,status:'uncertain'},b,true),/préparé/);assert.throws(()=>assertDeletionConfirmation({...row,prepared_plan:{hash:'abc',preparedAt:'invalid'}},b,true),/expiré/);
});
test('aperçu distingue structures personnes rapports et refuse les documents étrangers',()=>{
 const scope=planDeletion(snapshot,[],'s'),settings={settings:{contact_types:[{id:'c60_chw_site'},{id:'person',person:true}]}},site={_id:'s',_rev:'1',type:'contact',contact_type:'c60_chw_site',name:'Site'},person={_id:'p',_rev:'1',type:'person',name:'Nom privé',parent:{_id:'s'}},report={_id:'q',_rev:'1',type:'data_record',contact:{_id:'p'}};
 const p=deletionDocSummary([site,person,report],settings,scope);assert.equal(p.places,1);assert.equal(p.people,1);assert.equal(p.reports,1);assert.equal(p.documents.find(n=>n.id==='p').name,'Personne');
 assert.throws(()=>deletionDocSummary([site,{...person,parent:{_id:'other'}}],settings,scope),/hors/);assert.throws(()=>deletionDocSummary([site,{...report,contact:{_id:'other'}}],settings,scope),/hors/);assert.throws(()=>deletionDocSummary([site,{...person,contact_type:'bad',type:'contact'}],settings,scope),/inconnu/);
});
