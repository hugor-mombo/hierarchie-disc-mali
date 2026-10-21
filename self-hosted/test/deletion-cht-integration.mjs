// Official cht-conf against a disposable HTTP fixture. Never contacts live platforms.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {randomUUID,createHash} from 'node:crypto';
import {prepareDeletion,executeDeletion} from '../lib/deletion-executor.mjs';
import {planDeletion} from '../lib/deletion-plan.mjs';
const docs={};const add=(id,type,parent)=>docs[id]={_id:id,_rev:'1-qa',type:'contact',contact_type:type,name:id,...(parent?{parent:{_id:parent,...(docs[parent].parent?{parent:structuredClone(docs[parent].parent)}:{})}}:{})};
add('d0','c10_central');add('d1','c20_region','d0');add('d2','c30_district','d1');add('d3','c40_health_area','d2');add('d4','c50_supervision_area','d3');add('d5','c60_chw_site','d4');add('p5','c61_person','d5');
docs.r5={_id:'r5',_rev:'1-qa',type:'data_record',form:'qa',fields:{},contact:{_id:'p5',parent:structuredClone(docs.p5.parent)},_attachments:{'qa.txt':{content_type:'text/plain',data:Buffer.from('attachment').toString('base64')}}};
docs.q5={_id:'q5',_rev:'1-qa',type:'data_record',fields:{place_id:'d5'}};
const initial=structuredClone(docs);let writes=0,linked=false,partial=false;
const server=createServer(async(req,res)=>{const u=new URL(req.url,'http://localhost');let text='';for await(const chunk of req)text+=chunk;const b=text?JSON.parse(text):{};res.setHeader('Content-Type','application/json');const send=data=>res.end(JSON.stringify(data));
 if(u.pathname==='/'){send({couchdb:'Welcome',version:'3.3.3'});return;}
 if(u.pathname==='/_session'){res.setHeader('Set-Cookie','AuthSession=qa; Expires=Wed, 21 Oct 2037 12:00:00 GMT; Path=/');send({ok:true,name:'qa',roles:['_admin']});return;}
 if(u.pathname==='/api/deploy-info'){send({version:'4.12.0'});return;}
 if(u.pathname==='/medic'||u.pathname==='/medic/'){send({db_name:'medic',doc_count:Object.keys(docs).length,update_seq:1});return;}
 if(u.pathname==='/medic/settings'){send({settings:{contact_types:Object.values(initial).filter(d=>d.type==='contact').map(d=>({id:d.contact_type,person:d._id==='p5',parents:d.parent?[initial[d.parent._id].contact_type]:[]}))}});return;}
 if(u.pathname==='/api/v2/users'){send(linked&&u.searchParams.get('facility_id')==='d5'?[{username:'qa',place:{_id:'d5'}}]:[]);return;}
 if(u.pathname==='/medic/_all_docs'){const keys=b.keys||JSON.parse(u.searchParams.get('keys')||'[]');send({rows:keys.map(id=>({id,key:id,value:docs[id]?{rev:docs[id]._rev,...(docs[id]._deleted?{deleted:true}:{})}:undefined,...(u.searchParams.get('include_docs')==='true'&&docs[id]&&!docs[id]._deleted?{doc:docs[id]}:{})}))});return;}
 if(u.pathname.includes('/_view/')){let selected=[];const active=Object.values(docs).filter(d=>!d._deleted);
  if(u.pathname.endsWith('contacts_by_type')){const type=JSON.parse(u.searchParams.get('startkey'))[0];selected=active.filter(d=>d.contact_type===type);}
  if(u.pathname.endsWith('contacts_by_depth'))selected=active.filter(d=>['d4','d5','p5'].includes(d._id));
  if(u.pathname.endsWith('reports_by_subject')){const keys=b.keys||JSON.parse(u.searchParams.get('keys')||'[]');selected=active.filter(d=>keys.includes(d.fields?.place_id));}
  if(u.pathname.endsWith('reports_by_freetext'))selected=active.filter(d=>d._id==='r5');
  send({rows:selected.map(doc=>({id:doc._id,key:[doc.contact_type],value:1,doc}))});return;
 }
 if(u.pathname==='/medic/_bulk_docs'){writes++;send(b.docs.map((d,i)=>{if(partial&&i===1)return{id:d._id,error:'conflict'};if(docs[d._id]?._rev!==d._rev)return{id:d._id,error:'conflict'};docs[d._id]={...d,_rev:'2-qa'};return{id:d._id,rev:'2-qa',ok:true};}));return;}
 if(u.pathname.includes('/organisationUnitGroups/')){send({id:u.pathname.split('/').at(-1).replace('.json',''),organisationUnits:[]});return;}
 if(u.pathname.endsWith('/organisationUnitLevels.json')){send({organisationUnitLevels:[]});return;}
 if(u.pathname.endsWith('/organisationUnits.json')){send({pager:{pageCount:1,total:0},organisationUnits:[]});return;}
 const id=decodeURIComponent(u.pathname.slice('/medic/'.length));if(docs[id]&&!docs[id]._deleted){send(docs[id]);return;}
 res.statusCode=404;send({error:'not_found'});
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port,work=await mkdtemp(path.join(tmpdir(),'deletion-cht-qa-'));
const env={DISC_URL:base,DHIS_URL:base+'/dhis',DISC_USER:'qa',DISC_PASSWORD:'qa',DHIS_USER:'qa',DHIS_PASSWORD:'qa',ALLOW_HTTP_SOURCES:'true',ENABLE_REMOTE_WRITES:'true',WORK_DIRECTORY:work};
const snapshot={disc:Object.values(docs).filter(d=>d.type==='contact'&&d._id!=='p5').map(d=>({id:d._id,type:d.contact_type,name:d.name,parent:d.parent?._id||null})),dhis:[]};
const make=()=>({id:randomUUID(),unit_id:'d4',endpoint:base,reference_endpoint:base+'/dhis',scope:planDeletion(snapshot,[],'d4')});
try{
 let row=make();row.prepared_plan=await prepareDeletion(row,env,[]);assert.equal(writes,0);assert.equal(row.prepared_plan.places,2);assert.equal(row.prepared_plan.people,1);assert.equal(row.prepared_plan.reports,2);
 const backup=JSON.parse(await readFile(path.join(work,'deletions',row.id,'before',createHash('sha256').update('r5').digest('hex')+'.json'),'utf8'));assert.equal(backup._attachments['qa.txt'].data,Buffer.from('attachment').toString('base64'));
 linked=true;await assert.rejects(()=>executeDeletion(row,env,[]),/compte DISC/);assert.equal(writes,0);linked=false;
 docs.p5._rev='2-changed';await assert.rejects(()=>executeDeletion(row,env,[]),/modifiés/);assert.equal(writes,0);docs.p5._rev='1-qa';
 let marked=false;const result=await executeDeletion(row,env,[],()=>{marked=true;});assert.equal(result.documents,5);assert.ok(marked);assert.equal(writes,1);for(const id of ['d4','d5','p5','r5','q5'])assert.equal(docs[id]._deleted,true);assert.equal(docs.d3._deleted,undefined);
 Object.assign(docs,structuredClone(initial));row=make();row.prepared_plan=await prepareDeletion(row,env,[]);partial=true;marked=false;await assert.rejects(()=>executeDeletion(row,env,[],()=>{marked=true;}),/partielle/);assert.equal(marked,true);
 console.log('OK : CHT officiel, préparation sans écriture, personnes + rapports sujet/émetteur, pièces jointes sauvegardées, comptes et révisions bloquants, suppression récursive vérifiée, résultat partiel signalé.');
}finally{await new Promise(r=>server.close(r));await rm(work,{recursive:true,force:true});}
