import {query,transaction,audit} from './database.mjs';
import {prepareDeletion,executeDeletion} from './deletion-executor.mjs';
import {fetchDISC,fetchDHIS} from './sources.mjs';
import {saveSnapshot} from './state.mjs';
export async function recoverDeletionJobs(){await transaction(async c=>{const rows=await c.query("UPDATE deletion_requests SET status=CASE WHEN status='executing' THEN 'uncertain' ELSE 'failed' END,error='Worker interrompu : vérifier le résultat avant toute nouvelle demande.',updated_at=now() WHERE status IN ('preparing','executing') RETURNING id,status");for(const r of rows.rows)await audit(c,'worker','deletion-interrupted',r);});}
export async function processDeletionJob(){
 const row=await transaction(async c=>{const r=(await c.query("SELECT * FROM deletion_requests WHERE status IN ('prepare_queued','queued') ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1")).rows[0];if(!r)return null;r.status=r.status==='prepare_queued'?'preparing':'executing';await c.query('UPDATE deletion_requests SET status=$2,updated_at=now() WHERE id=$1',[r.id,r.status]);await audit(c,'worker','deletion-'+r.status,{id:r.id});return r;});
 if(!row)return false;let wrote=false;
 try{
  const authorize=async()=>{const u=(await query('SELECT role,enabled,must_change_password FROM app_users WHERE id=$1',[row.status==='preparing'?row.requested_by:row.executor])).rows[0];if(!u?.enabled||u.must_change_password||!(row.status==='preparing'?['editor','reviewer','admin']:['admin']).includes(u.role))throw Error('Droits de suppression ou de préparation révoqués.');};
  await authorize();const maps=(await query('SELECT disc_id AS "discId",dhis_id AS "dhisId" FROM unit_mappings')).rows;
  if(row.status==='preparing'){
   const plan=await prepareDeletion(row,process.env,maps);await transaction(async c=>{await c.query("UPDATE deletion_requests SET status='prepared',prepared_plan=$2,error=NULL,updated_at=now() WHERE id=$1",[row.id,JSON.stringify(plan)]);await audit(c,'worker','deletion-prepared',{id:row.id,hash:plan.hash,places:plan.places,people:plan.people,reports:plan.reports});});
  }else{
   const result=await executeDeletion(row,process.env,maps,()=>{wrote=true;},authorize);
   await transaction(async c=>{await c.query("UPDATE deletion_requests SET status='succeeded',result=$2,error=NULL,updated_at=now() WHERE id=$1",[row.id,JSON.stringify(result)]);await audit(c,'worker','deletion-succeeded',{id:row.id,...result});});
   try{const [disc,dhis]=await Promise.all([fetchDISC(process.env),fetchDHIS(process.env)]);await saveSnapshot(disc,dhis.nodes,dhis.levels,'worker');}catch{await audit({query},'worker','refresh-required',{id:row.id});}
  }
 }catch(e){const status=wrote?'uncertain':'failed';await transaction(async c=>{await c.query('UPDATE deletion_requests SET status=$2,error=$3,updated_at=now() WHERE id=$1',[row.id,status,String(e.message).slice(0,300)]);await audit(c,'worker','deletion-'+status,{id:row.id,error:String(e.message).slice(0,300)});});console.error('Suppression '+row.id+' arrêtée ; consulter son statut.');}
 return true;
}
