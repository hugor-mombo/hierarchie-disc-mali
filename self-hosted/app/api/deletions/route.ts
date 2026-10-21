import {randomUUID} from 'node:crypto';
import {transaction,audit} from '../../../lib/database.mjs';
import {readState} from '../../../lib/state.mjs';
import {sourceURL} from '../../../lib/sources.mjs';
import {planDeletion,assertDeletionConfirmation} from '../../../lib/deletion-plan.mjs';
import {requireUser,apiError} from '../../../lib/auth.mjs';
import {assertOrigin} from '../../../lib/security.mjs';
export const runtime='nodejs';
export async function POST(r:Request){try{
 assertOrigin(r);const b=await r.json(),u=await requireUser(r,b.action==='execute'?'execute':'edit');
 await transaction(async(c:any)=>{
  await c.query("SELECT pg_advisory_xact_lock(hashtext('hierarchie:sync-queue'))");
  if(b.action==='prepare'){
   if(typeof b.reason!=='string'||b.reason.trim().length<10||b.reason.length>2000)throw Error('Justification de 10 à 2 000 caractères requise.');
   const open=await c.query("SELECT 1 FROM deletion_requests WHERE status NOT IN ('succeeded','failed','cancelled') UNION ALL SELECT 1 FROM sync_requests WHERE status NOT IN ('succeeded','failed','cancelled') UNION ALL SELECT 1 FROM move_requests WHERE status NOT IN ('succeeded','failed','cancelled','rejected') LIMIT 1");
   if(open.rowCount)throw Error('Terminer ou annuler les opérations ouvertes avant de préparer une suppression. Un résultat incertain doit être contrôlé manuellement.');
   const snapshot=(await c.query("SELECT value FROM app_records WHERE key='snapshot'")).rows[0]?.value;
   const maps=(await c.query('SELECT disc_id AS "discId",dhis_id AS "dhisId" FROM unit_mappings')).rows;
   const scope=planDeletion(snapshot,maps,b.unitId),id=randomUUID();
   await c.query("INSERT INTO deletion_requests(id,unit_id,unit_name,reason,endpoint,reference_endpoint,scope,status,requested_by) VALUES($1,$2,$3,$4,$5,$6,$7,'prepare_queued',$8)",[id,scope.unitId,scope.name,b.reason.trim(),sourceURL(process.env,'disc'),sourceURL(process.env,'dhis'),JSON.stringify(scope),u.id]);
   await audit(c,u.id,'deletion-prepare',{id,unitId:scope.unitId,structures:scope.units.length});
  }else if(['execute','cancel'].includes(b.action)){
   const row=(await c.query('SELECT * FROM deletion_requests WHERE id=$1 FOR UPDATE',[b.id])).rows[0];if(!row)throw Error('Demande inconnue.');
   if(b.action==='cancel'){
    if(!['prepare_queued','prepared'].includes(row.status))throw Error('Une suppression en cours ou incertaine ne peut pas être annulée.');
    if(row.requested_by!==u.id&&u.role!=='admin')throw Error('Annulation réservée au demandeur ou à un administrateur.');
   }else assertDeletionConfirmation(row,b,process.env.ENABLE_REMOTE_WRITES==='true');
   await c.query('UPDATE deletion_requests SET status=$2,executor=$3,updated_at=now() WHERE id=$1',[row.id,b.action==='execute'?'queued':'cancelled',b.action==='execute'?u.id:null]);
   await audit(c,u.id,'deletion-'+b.action,{id:row.id,hash:row.prepared_plan?.hash,structures:row.prepared_plan?.places,people:row.prepared_plan?.people,reports:row.prepared_plan?.reports});
  }else throw Error('Action inconnue.');
 });
 return Response.json({...await readState(),user:u},{headers:{'Cache-Control':'no-store'}});
}catch(e){return apiError(e);}}
