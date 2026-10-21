// Dedicated disposable QA stack only. No live platform request is made.
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
if(!process.env.DATABASE_URL||!new URL(process.env.DATABASE_URL).pathname.endsWith('_qa')||process.env.DISC_URL!=='https://disc.example'||process.env.DHIS_URL!=='https://dhis.example/dhis')throw Error('Stack de recette dédiée requise.');
const {query,pool}=await import('../lib/database.mjs'),{hashPassword}=await import('../lib/security.mjs'),{demoState}=await import('../lib/demo.mjs'),{recoverDeletionJobs,processDeletionJob}=await import('../lib/deletion-worker.mjs');
const base='http://web:3000',origin=process.env.APP_URL,password='QA-'+randomUUID(),hash=await hashPassword(password),users={};
async function api(body,cookie,endpoint='/api/deletions'){const r=await fetch(base+endpoint,{method:'POST',headers:{'Content-Type':'application/json',Origin:origin,...(cookie?{cookie}:{})},body:JSON.stringify(body)});return{status:r.status,data:await r.json()};}
try{
 for(const role of ['viewer','editor','admin']){const id=randomUUID(),username='delete-qa-'+role;await query('INSERT INTO app_users(id,username,display_name,password_hash,role,must_change_password) VALUES($1,$2,$3,$4,$3,false)',[id,username,role,hash]);const r=await fetch(base+'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json',Origin:origin},body:JSON.stringify({username,password})});assert.equal(r.status,200);users[role]={id,cookie:r.headers.get('set-cookie').split(';')[0]};}
 const s=demoState();await query("INSERT INTO app_records(key,value) VALUES('snapshot',$1) ON CONFLICT(key) DO UPDATE SET value=excluded.value",[JSON.stringify(s.snapshot)]);for(const m of s.mappings)await query('INSERT INTO unit_mappings(disc_id,dhis_id,actor) VALUES($1,$2,$3)',[m.discId,m.dhisId,'qa']);
 const input={action:'prepare',unitId:'d11',reason:'Suppression de la branche fictive absente du référentiel.'};
 assert.equal((await api(input)).status,401);assert.equal((await api(input,users.viewer.cookie)).status,403);assert.notEqual((await api({...input,unitId:'d0'},users.editor.cookie)).status,200);assert.notEqual((await api({...input,unitId:'d6'},users.editor.cookie)).status,200);
 let r=await api(input,users.editor.cookie);assert.equal(r.status,200,JSON.stringify(r.data));let row=r.data.deletions[0];assert.equal(row.status,'prepare_queued');
 assert.notEqual((await api(input,users.editor.cookie)).status,200);
 for(const [endpoint,body] of [['/api/sync',{action:'add',originSource:'dhis',originId:'h11',operation:'create',parentId:'d4',reason:input.reason}],['/api/moves',{action:'propose',source:'disc',unitId:'d11',parentId:'d4',reason:input.reason}],['/api/actions',{action:'approve',discId:'d8',dhisId:'h8'}]]){const blocked=await api(body,users.editor.cookie,endpoint);assert.notEqual(blocked.status,200);assert.match(blocked.data.error,/suppression DISC/);}
 assert.equal((await api({action:'cancel',id:row.id},users.editor.cookie)).status,200);
 r=await api(input,users.editor.cookie);assert.equal(r.status,200);row=r.data.deletions.find(d=>d.status==='prepare_queued');
 const confirm={action:'execute',id:row.id,planHash:'qa-hash',confirmName:row.unit_name,confirmed:true,backupConfirmed:true,dataConfirmed:true};
 assert.equal((await api(confirm,users.editor.cookie)).status,403);assert.notEqual((await api(confirm,users.admin.cookie)).status,200);
 await query("UPDATE deletion_requests SET status='prepared',prepared_plan=$2 WHERE id=$1",[row.id,JSON.stringify({hash:'qa-hash',preparedAt:new Date().toISOString(),places:1,people:2,reports:3,documents:[]})]);
 for(const body of [{...confirm,planHash:'changed'},{...confirm,confirmName:'wrong'},{...confirm,dataConfirmed:false},{...confirm,backupConfirmed:false}])assert.notEqual((await api(body,users.admin.cookie)).status,200);
 r=await api(confirm,users.admin.cookie);assert.equal(r.status,200,JSON.stringify(r.data));assert.equal(r.data.deletions.find(d=>d.id===row.id).status,'queued');
 // A revoked administrator must stop execution before contacting a platform.
 await query('UPDATE app_users SET enabled=false WHERE id=$1',[users.admin.id]);const realFetch=globalThis.fetch;globalThis.fetch=()=>{throw Error('Unexpected remote request');};try{await processDeletionJob();}finally{globalThis.fetch=realFetch;}
 assert.equal((await query('SELECT status FROM deletion_requests WHERE id=$1',[row.id])).rows[0].status,'failed');
 await query('UPDATE app_users SET enabled=true WHERE id=$1',[users.admin.id]);
 await query("UPDATE deletion_requests SET status='preparing' WHERE id=$1",[row.id]);await recoverDeletionJobs();assert.equal((await query('SELECT status FROM deletion_requests WHERE id=$1',[row.id])).rows[0].status,'failed');
 await query("UPDATE deletion_requests SET status='executing' WHERE id=$1",[row.id]);await recoverDeletionJobs();assert.equal((await query('SELECT status FROM deletion_requests WHERE id=$1',[row.id])).rows[0].status,'uncertain');
 assert.notEqual((await api({action:'cancel',id:row.id},users.admin.cookie)).status,200);assert.notEqual((await api(input,users.editor.cookie)).status,200);
 console.log('OK : migration, authentification, rôles, racine et mappings protégés, plan et confirmations exigés, annulation, exclusion des opérations concurrentes, révocation avant écriture et reprise incertaine sans relance.');
}finally{await query('DELETE FROM deletion_requests');await query('DELETE FROM unit_mappings');await query('DELETE FROM app_records');for(const user of Object.values(users))await query('DELETE FROM app_users WHERE id=$1',[user.id]);await pool().end();}
