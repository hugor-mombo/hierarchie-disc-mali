import {spawn} from 'node:child_process';
import {mkdir,readFile,writeFile,readdir} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {remote,assertWritesEnabled} from './move-executor.mjs';
import {fetchDISC,fetchDHIS,sourceURL} from './sources.mjs';
import {planDeletion,deletionDocSummary} from './deletion-plan.mjs';
import {assertSamePlan} from './sync-plan.mjs';
const canonical=v=>Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v;
const digest=value=>createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex');
function directory(row,env){if(!/^[a-f0-9-]{36}$/.test(row.id))throw Error('Demande invalide.');return path.join(env.WORK_DIRECTORY||'/var/lib/hierarchie','deletions',row.id);}
async function originals(ids,env){const docs=[];for(let i=0;i<ids.length;i+=100){const r=await remote('disc','/medic/_all_docs?include_docs=true',env,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keys:ids.slice(i,i+100)})});const data=await r.json();if(!Array.isArray(data.rows)||data.rows.length!==ids.slice(i,i+100).length)throw Error('Précontrôle incomplet.');for(let j=0;j<data.rows.length;j++){let d=data.rows[j].doc;if(!d||d._deleted||d._id!==ids[i+j])throw Error('Document modifié ou absent.');if(d._attachments){const full=await (await remote('disc','/medic/'+encodeURIComponent(d._id)+'?attachments=true',env)).json();if(full._id!==d._id||full._rev!==d._rev||Object.keys(d._attachments).sort().join()!==Object.keys(full._attachments||{}).sort().join()||Object.values(full._attachments||{}).some(a=>typeof a.data!=='string'))throw Error('Sauvegarde complète des pièces jointes impossible.');d=full;}docs.push(d);}}return docs;}
async function linkedAccounts(ids,env){
 // Same CHT user lookup used by cht-conf; avoids reading password hashes from _users.
 for(const id of ids){const data=await (await remote('disc','/api/v2/users?facility_id='+encodeURIComponent(id),env)).json();
  if(!Array.isArray(data))throw Error('Contrôle des comptes DISC incomplet.');
  if(data.length)throw Error('Un compte DISC est rattaché à cette branche. Réaffecter ou traiter ce compte avant suppression.');
 }
}
async function runCHT(row,env,dir,verifyIds){
 let verifyFile;if(verifyIds){await mkdir(dir,{recursive:true,mode:0o700});verifyFile=path.join(dir,'ids.json');await writeFile(verifyFile,JSON.stringify(verifyIds),{mode:0o600});}
 await new Promise((resolve,reject)=>{const child=spawn(process.execPath,[new URL('../scripts/cht-delete-stage.cjs',import.meta.url).pathname],{env:{...process.env,...env,DELETE_UNIT:row.unit_id,DELETE_DIRECTORY:dir,...(verifyIds?{DELETE_VERIFY_FILE:verifyFile}:{})},stdio:['ignore','ignore','ignore']});const timer=setTimeout(()=>{child.kill('SIGKILL');reject(Error('Préparation CHT trop longue.'));},3600000);child.once('error',()=>{clearTimeout(timer);reject(Error('Préparation CHT indisponible.'));});child.once('exit',code=>{clearTimeout(timer);code===0?resolve():reject(Error('Préparation de suppression CHT refusée. Vérifier les droits et la hiérarchie.'));});});
 }
async function prepareFiles(row,env,name){
 const dir=path.join(directory(row,env),name);await mkdir(dir,{recursive:true,mode:0o700});await runCHT(row,env,dir);
 const files=await readdir(dir,{withFileTypes:true}),deletes=[];
 for(const f of files){if(!f.isFile()||!f.name.endsWith('.doc.json'))throw Error('Fichier de plan inattendu.');const d=JSON.parse(await readFile(path.join(dir,f.name),'utf8'));if(!d._id||!d._rev||d._deleted!==true||d.cht_disable_linked_users)throw Error('Plan de suppression invalide.');deletes.push(d);}
 deletes.sort((a,b)=>a._id.localeCompare(b._id));if(!deletes.length||deletes.length>50000||new Set(deletes.map(d=>d._id)).size!==deletes.length)throw Error('Périmètre de suppression vide, dupliqué ou trop grand.');
 return deletes;
}
export async function inspectDeletion(row,env,mappings,name='prepared'){
 if(sourceURL(env,'disc')!==row.endpoint||sourceURL(env,'dhis')!==row.reference_endpoint)throw Error('La destination DISC a changé.');
 const [disc,dhis]=await Promise.all([fetchDISC(env),fetchDHIS(env)]);
 const scope=planDeletion({disc,dhis:dhis.nodes},mappings,row.unit_id);assertSamePlan(row.scope,scope);
 const deletes=await prepareFiles(row,env,name),docs=await originals(deletes.map(d=>d._id),env);
 if(docs.some((d,i)=>d._rev!==deletes[i]._rev))throw Error('Révision modifiée pendant la préparation.');
 const settings=await (await remote('disc','/medic/settings',env)).json();
 const summary=deletionDocSummary(docs,settings,scope),ids=new Set(summary.documents.filter(d=>d.kind!=='report').map(d=>d.id));
 await linkedAccounts(ids,env);
 // Do not leave an ancestor referencing a removed primary contact.
 const root=disc.find(n=>n.id===row.unit_id),anc=[];let parent=root.parent;while(parent){if(anc.includes(parent))throw Error('Cycle dans les parents.');anc.push(parent);parent=disc.find(n=>n.id===parent)?.parent;}
 for(const ancestor of await originals(anc,env)){if(ids.has(typeof ancestor.contact==='string'?ancestor.contact:ancestor.contact?._id))throw Error('Un parent utilise un contact de cette branche comme contact principal. Réaffecter ce contact principal avant suppression.');}
 const hash=digest({scope,summary,deletes,beforeHashes:docs.map(d=>digest(d))});
 return {scope,summary,hash,deletes,docs};
}
export async function prepareDeletion(row,env,mappings){
 const inspection=await inspectDeletion(row,env,mappings),dir=path.join(directory(row,env),'before');await mkdir(dir,{recursive:true,mode:0o700});
 for(const d of inspection.docs)await writeFile(path.join(dir,createHash('sha256').update(d._id).digest('hex')+'.json'),JSON.stringify(d),{mode:0o600});
 await writeFile(path.join(directory(row,env),'payload.json'),JSON.stringify(inspection.deletes),{mode:0o600});
 return {...inspection.summary,hash:inspection.hash,preparedAt:new Date().toISOString(),engine:'cht-conf@6.6.1 recursive deletion',backupDirectory:dir};
}
export async function executeDeletion(row,env,mappings,onWrite=()=>{},authorize=async()=>{}){
 assertWritesEnabled(env);const plan=row.prepared_plan,age=Date.now()-Date.parse(plan?.preparedAt);if(!Number.isFinite(age)||age>3600000)throw Error('Plan expiré.');
 const inspection=await inspectDeletion(row,env,mappings,'verification');if(inspection.hash!==plan.hash)throw Error('Contacts, rapports ou périmètre modifiés depuis la préparation. Préparer une nouvelle demande.');
 const payload=JSON.parse(await readFile(path.join(directory(row,env),'payload.json'),'utf8'));if(digest(payload)!==digest(inspection.deletes))throw Error('Plan sauvegardé modifié.');
 for(const doc of inspection.docs){const saved=JSON.parse(await readFile(path.join(directory(row,env),'before',createHash('sha256').update(doc._id).digest('hex')+'.json'),'utf8'));if(digest(saved)!==digest(doc))throw Error('Sauvegarde absente ou modifiée.');}
 await authorize();
 // Preflight every revision before the first write. Writes can still conflict with
 // concurrent offline sync: partial outcomes become uncertain, never auto-retried.
 const current=await originals(payload.map(d=>d._id),env);if(current.some((d,i)=>d._rev!==payload[i]._rev))throw Error('Révision modifiée avant suppression.');
 for(let i=0;i<payload.length;i+=100){await authorize();onWrite();const result=await (await remote('disc','/medic/_bulk_docs',env,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({docs:payload.slice(i,i+100)})})).json();if(!Array.isArray(result)||result.length!==payload.slice(i,i+100).length||result.some((r,j)=>r.ok!==true||r.error||r.id!==payload[i+j]._id))throw Error('Suppression partielle ou conflit : contrôle manuel obligatoire, aucun nouvel essai automatique.');}
 for(let i=0;i<payload.length;i+=100){const keys=payload.slice(i,i+100).map(d=>d._id);const data=await (await remote('disc','/medic/_all_docs',env,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keys})})).json();if(!Array.isArray(data.rows)||data.rows.length!==keys.length||data.rows.some((r,j)=>r.key!==keys[j]||r.value?.deleted!==true))throw Error('Suppression non vérifiable : contrôle manuel requis.');}
 await runCHT(row,env,path.join(directory(row,env),'postverify'),inspection.summary.documents.filter(d=>d.kind!=='report').map(d=>d.id));
 await linkedAccounts(new Set(inspection.summary.documents.filter(d=>d.kind!=='report').map(d=>d.id)),env);
 return {verifiedAt:new Date().toISOString(),documents:payload.length,places:plan.places,people:plan.people,reports:plan.reports};
}
