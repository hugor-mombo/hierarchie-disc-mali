// Run only against the dedicated QA Compose stack, never against a live registry.
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
if(!process.env.DATABASE_URL||!new URL(process.env.DATABASE_URL).pathname.endsWith('_qa')||process.env.DISC_URL!=='https://disc.example'||process.env.DHIS_URL!=='https://dhis.example/dhis')throw Error('Stack de recette dédiée requise.');
const {query,pool}=await import('../lib/database.mjs'),{hashPassword}=await import('../lib/security.mjs');
const {processSyncJob,recoverSyncJobs}=await import('../lib/sync-worker.mjs');
const {fixture}=await import('./fixtures/sync-platforms.mjs');
const base=process.env.QA_APP_URL||'http://web:3000',origin=process.env.APP_URL||base,password='QA-'+randomUUID(),hash=await hashPassword(password),users={};
const work=await mkdtemp(path.join(tmpdir(),'sync-worker-qa-'));process.env.WORK_DIRECTORY=work;
const realFetch=globalThis.fetch;
async function api(body,cookie){const r=await realFetch(base+'/api/sync',{method:'POST',headers:{'Content-Type':'application/json',Origin:origin,...(cookie?{cookie}:{})},body:JSON.stringify(body)});return{status:r.status,data:await r.json()};}
async function seed(){
  await query('DELETE FROM sync_requests');await query('DELETE FROM unit_mappings');
  const f=await fixture(work);
  await query("INSERT INTO app_records(key,value) VALUES('snapshot',$1),('levels',$2) ON CONFLICT(key) DO UPDATE SET value=excluded.value",[JSON.stringify(f.s.snapshot),JSON.stringify(f.s.levels)]);
  for(const m of f.s.mappings)await query('INSERT INTO unit_mappings(disc_id,dhis_id,actor) VALUES($1,$2,$3)',[m.discId,m.dhisId,'qa']);
  return f;
}
try{
  for(const role of ['viewer','editor','admin']){
    const id=randomUUID(),username='qa-'+role+'-'+Date.now();
    await query('INSERT INTO app_users(id,username,display_name,password_hash,role,must_change_password) VALUES($1,$2,$3,$4,$3,false)',[id,username,role,hash]);
    const r=await realFetch(base+'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json',Origin:origin},body:JSON.stringify({username,password})});assert.equal(r.status,200);users[role]={id,cookie:r.headers.get('set-cookie').split(';')[0]};
  }
  let f=await seed();
  const input={originSource:'dhis',originId:'h11',operation:'create',parentId:'d4',reason:'Créer la structure manquante en recette.'};
  assert.equal((await api({...input,action:'add'})).status,401);
  assert.equal((await api({...input,action:'add'},users.viewer.cookie)).status,403);
  let r=await api({...input,action:'add'},users.editor.cookie);assert.equal(r.status,200,JSON.stringify(r.data));
  let row=r.data.syncRequests[0];assert.equal(row.status,'draft');assert.equal(r.data.truthSource,'dhis');
  assert.equal((await api({...input,action:'add'},users.editor.cookie)).status,400);
  assert.equal((await api({action:'execute',ids:[row.id],confirmed:true,backupConfirmed:true,maintenanceConfirmed:true},users.editor.cookie)).status,403);
  assert.equal((await api({action:'execute',ids:[row.id]},users.admin.cookie)).status,400);
  assert.equal((await api({action:'execute',ids:[row.id],confirmed:true,backupConfirmed:true,maintenanceConfirmed:true},users.admin.cookie)).status,200);
  globalThis.fetch=f.fetcher;await processSyncJob();globalThis.fetch=realFetch;
  row=(await query('SELECT * FROM sync_requests WHERE id=$1',[row.id])).rows[0];assert.equal(row.status,'succeeded',row.error);assert.equal(row.target_id,'created-qa');assert.equal((await query("SELECT dhis_id FROM unit_mappings WHERE disc_id='created-qa'")).rows[0].dhis_id,'h11');
  console.log('OK : API protégée, confirmation, file, création DISC par le worker et mapping après vérification.');
  f=await seed();r=await api({...input,action:'execute-now',confirmed:true,backupConfirmed:true,maintenanceConfirmed:true},users.admin.cookie);assert.equal(r.status,400);
  const reviewed=f.row(input).plan;delete reviewed.endpoints;
  r=await api({...input,action:'execute-now',reviewPlan:reviewed,confirmed:true,backupConfirmed:true,maintenanceConfirmed:true},users.admin.cookie);assert.equal(r.status,200,JSON.stringify(r.data));row=r.data.syncRequests[0];
  await query("UPDATE app_users SET role='viewer' WHERE id=$1",[users.admin.id]);
  globalThis.fetch=f.fetcher;await processSyncJob();globalThis.fetch=realFetch;
  assert.equal((await query('SELECT status FROM sync_requests WHERE id=$1',[row.id])).rows[0].status,'failed');assert.equal(f.writes.length,0);
  await query("UPDATE app_users SET role='admin' WHERE id=$1",[users.admin.id]);
  console.log('OK : plan présenté exigé et droits revérifiés par le worker.');
  f=await seed();const reverse={originSource:'disc',originId:'d10',operation:'create',parentId:'h4',reason:'Création DHIS2 en recette uniquement.'},rp=f.row(reverse).plan;delete rp.endpoints;
  r=await api({...reverse,action:'execute-now',reviewPlan:rp,confirmed:true,backupConfirmed:true,maintenanceConfirmed:true},users.admin.cookie);assert.equal(r.status,200,JSON.stringify(r.data));row=r.data.syncRequests[0];
  f.fail();globalThis.fetch=f.fetcher;await processSyncJob();globalThis.fetch=realFetch;
  assert.equal((await query('SELECT status FROM sync_requests WHERE id=$1',[row.id])).rows[0].status,'uncertain');
  assert.equal((await api({...reverse,action:'add'},users.editor.cookie)).status,400);
  assert.equal(await processSyncJob(),false);
  console.log('OK : réponse perdue après création → contrôle manuel, aucune relance et doublon bloqué.');
  await query("UPDATE sync_requests SET status='executing' WHERE id=$1",[row.id]);await recoverSyncJobs();assert.equal((await query('SELECT status FROM sync_requests WHERE id=$1',[row.id])).rows[0].status,'uncertain');
  console.log('OK : interruption du worker signalée sans rejouer les écritures.');
}finally{globalThis.fetch=realFetch;await pool().end();await rm(work,{recursive:true,force:true});}
