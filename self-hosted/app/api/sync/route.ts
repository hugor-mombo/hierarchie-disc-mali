import {randomUUID} from 'node:crypto';
import {transaction,audit} from '../../../lib/database.mjs';
import {readState} from '../../../lib/state.mjs';
import {sourceURL} from '../../../lib/sources.mjs';
import {planSync,assertSamePlan} from '../../../lib/sync-plan.mjs';
import {requireUser,apiError} from '../../../lib/auth.mjs';
import {assertOrigin} from '../../../lib/security.mjs';
export const runtime='nodejs';
export async function POST(r:Request){try{
  assertOrigin(r);const b=await r.json(),u=await requireUser(r,['execute','execute-now'].includes(b.action)?'execute':'edit');
  await transaction(async(c:any)=>{
    // Serialise registry changes with the worker and legacy move queue.
    await c.query("SELECT pg_advisory_xact_lock(hashtext('hierarchie:sync-queue'))");
    if(['add','execute-now'].includes(b.action)){if((await c.query("SELECT 1 FROM deletion_requests WHERE status NOT IN ('succeeded','failed','cancelled') LIMIT 1")).rowCount)throw Error('Une suppression DISC est ouverte. La terminer ou annuler son plan avant de préparer une autre opération.');
      if(typeof b.reason!=='string'||b.reason.trim().length<10||b.reason.length>2000)throw Error('Justification de 10 à 2 000 caractères requise.');
      const snapshot=(await c.query("SELECT value FROM app_records WHERE key='snapshot'")).rows[0]?.value;
      const levels=(await c.query("SELECT value FROM app_records WHERE key='levels'")).rows[0]?.value;
      const maps=(await c.query('SELECT disc_id AS "discId",dhis_id AS "dhisId" FROM unit_mappings')).rows;
      const plan:any=planSync(snapshot,maps,levels||undefined,b),id=randomUUID();
      if(b.action==='execute-now')assertSamePlan(b.reviewPlan,plan);
      plan.endpoints={disc:sourceURL(process.env,'disc'),dhis:sourceURL(process.env,'dhis')};
      const conflict=await c.query("SELECT 1 FROM move_requests WHERE source=$1 AND unit_id=$2 AND status NOT IN ('succeeded','failed','rejected','cancelled')",[plan.targetSource,plan.target?.id||'']);
      if(conflict.rowCount)throw Error('Un déplacement de cette unité est déjà en cours.');
      const overlap=await c.query("SELECT 1 FROM sync_requests WHERE status NOT IN ('succeeded','failed','cancelled') AND ((origin_source=$1 AND origin_id=$2) OR (target_source=$1 AND target_id=$2) OR (origin_source=$3 AND origin_id=$4) OR (target_source=$3 AND target_id=$4))",[plan.originSource,plan.origin.id,plan.targetSource,plan.target?.id||'']);
      if(overlap.rowCount)throw Error('Une action ouverte ou incertaine concerne déjà cette unité.');
      if(b.action==='execute-now')confirmExecution(b);
      await c.query('INSERT INTO sync_requests(id,origin_source,target_source,origin_id,target_id,operation,plan,reason,requested_by,status,executor) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)',[id,plan.originSource,plan.targetSource,plan.origin.id,plan.target?.id||null,plan.operation,JSON.stringify(plan),b.reason.trim(),u.id,b.action==='execute-now'?'queued':'draft',b.action==='execute-now'?u.id:null]);
      await audit(c,u.id,'sync-'+b.action,{id,target:plan.targetSource,operation:plan.operation,originId:plan.origin.id,confirmation:b.action==='execute-now'});
    }else if(['execute','cancel'].includes(b.action)){
      if(!Array.isArray(b.ids)||!b.ids.length||b.ids.length>100||new Set(b.ids).size!==b.ids.length)throw Error('Sélection de 1 à 100 actions requise.');
      if(b.action==='execute')confirmExecution(b);
      for(const id of b.ids){
        const row=(await c.query('SELECT * FROM sync_requests WHERE id=$1 FOR UPDATE',[id])).rows[0];
        if(!row||row.status!=='draft')throw Error('Seules les actions à confirmer peuvent être exécutées ou annulées.');
        if(b.action==='cancel'&&row.requested_by!==u.id&&u.role!=='admin')throw Error('Annulation réservée au demandeur ou à un administrateur.');
        await c.query('UPDATE sync_requests SET status=$2,executor=$3,updated_at=now() WHERE id=$1',[id,b.action==='execute'?'queued':'cancelled',b.action==='execute'?u.id:null]);
        await audit(c,u.id,'sync-'+b.action,{id,confirmation:b.action==='execute'});
      }
    }else throw Error('Action inconnue.');
  });
  return Response.json({...await readState(),user:u},{headers:{'Cache-Control':'no-store'}});
}catch(e){return apiError(e);}}
function confirmExecution(b:any){
  if(process.env.ENABLE_REMOTE_WRITES!=='true')throw Error('Les écritures distantes sont désactivées sur le serveur.');
  if(b.confirmed!==true||b.backupConfirmed!==true||b.maintenanceConfirmed!==true)throw Error('Confirmer les opérations, la sauvegarde et la disponibilité de la plateforme avant exécution.');
}
