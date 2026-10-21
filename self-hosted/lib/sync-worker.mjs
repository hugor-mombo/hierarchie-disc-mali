import {query,transaction,audit} from './database.mjs';
import {executeSync} from './sync-executor.mjs';
import {fetchDISC,fetchDHIS} from './sources.mjs';
import {saveSnapshot} from './state.mjs';
export async function recoverSyncJobs(){
  await transaction(async c=>{
    const rows=await c.query("UPDATE sync_requests SET status='uncertain',error='Worker interrompu : vérifier la plateforme avant toute nouvelle action.',updated_at=now() WHERE status='executing' RETURNING id");
    for(const row of rows.rows)await audit(c,'worker','sync-interrupted',{id:row.id});
  });
}
export async function processSyncJob(){
  const row=await transaction(async c=>{
    const r=(await c.query("SELECT * FROM sync_requests WHERE status='queued' ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1")).rows[0];
    if(!r)return null;
    await c.query("UPDATE sync_requests SET status='executing',updated_at=now() WHERE id=$1",[r.id]);
    await audit(c,'worker','sync-executing',{id:r.id});return r;
  });
  if(!row)return false;
  let wrote=false;
  try{
    async function authorize(){const user=(await query('SELECT role,enabled,must_change_password FROM app_users WHERE id=$1',[row.executor])).rows[0];if(!user?.enabled||user.role!=='admin'||user.must_change_password)throw Error('Droit d’exécution révoqué ou mot de passe à renouveler.');}
    await authorize();
    const maps=(await query('SELECT disc_id AS "discId",dhis_id AS "dhisId" FROM unit_mappings')).rows;
    const levels=(await query("SELECT value FROM app_records WHERE key='levels'")).rows[0]?.value;
    const result=await executeSync(row,process.env,maps,levels,()=>{wrote=true;},authorize);
    await transaction(async c=>{
      if(row.operation==='create'){
        const discId=row.target_source==='disc'?result.targetId:row.origin_id,dhisId=row.target_source==='dhis'?result.targetId:row.origin_id;
        await c.query("SELECT pg_advisory_xact_lock(hashtext('hierarchie:mappings'))");
        await c.query('INSERT INTO unit_mappings(disc_id,dhis_id,actor) VALUES($1,$2,$3)',[discId,dhisId,row.executor]);
      }
      await c.query("UPDATE sync_requests SET status='succeeded',target_id=$2,result=$3,error=NULL,updated_at=now() WHERE id=$1",[row.id,result.targetId,JSON.stringify(result)]);
      await audit(c,'worker','sync-succeeded',{id:row.id,...result});
    });
    try{const [disc,dhis]=await Promise.all([fetchDISC(process.env),fetchDHIS(process.env)]);await saveSnapshot(disc,dhis.nodes,dhis.levels,'worker',dhis.groupsRead);}
    catch{await audit({query},'worker','refresh-required',{id:row.id});}
  }catch(e){
    const status=wrote?'uncertain':'failed';
    await transaction(async c=>{
      await c.query('UPDATE sync_requests SET status=$2,error=$3,updated_at=now() WHERE id=$1',[row.id,status,String(e.message).slice(0,240)]);
      await audit(c,'worker','sync-'+status,{id:row.id,error:String(e.message).slice(0,240)});
    });
    console.error('Synchronisation '+row.id+' arrêtée ; consulter son statut.');
  }
  return true;
}
