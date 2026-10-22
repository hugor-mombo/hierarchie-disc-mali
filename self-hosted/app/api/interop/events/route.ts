import {createHash} from 'node:crypto';
import {transaction,audit} from '../../../../lib/database.mjs';
import {authorizeInterop,validateInteropEvent,interopError} from '../../../../lib/interop.mjs';
import {apiError} from '../../../../lib/auth.mjs';
export async function POST(request:Request){try{
 authorizeInterop(request,'write');
 if(Number(request.headers.get('content-length')||0)>16384)throw interopError('Événement trop volumineux.',413);
 const reader=request.body?.getReader();if(!reader)throw interopError('Événement requis.');
 let size=0;const chunks:Uint8Array[]=[];
 while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>16384){await reader.cancel();throw interopError('Événement trop volumineux.',413);}chunks.push(value);}
 const input=JSON.parse(Buffer.concat(chunks).toString('utf8'));
 const duplicate=await transaction(async(c:any)=>{
  const manifest=(await c.query('SELECT document FROM interop_manifests WHERE version=$1',[typeof input?.mappingVersion==='string'?input.mappingVersion:''])).rows[0]?.document;
  const event=validateInteropEvent(input,manifest),hash=createHash('sha256').update(JSON.stringify(event)).digest('hex');
  const inserted=await c.query('INSERT INTO interop_events(event_id,payload_hash,run_id,mapping_version,payload) VALUES($1,$2,$3,$4,$5) ON CONFLICT(event_id) DO NOTHING RETURNING id',[event.eventId,hash,event.runId,event.mappingVersion,JSON.stringify(event)]);
  if(!inserted.rowCount){const old=(await c.query('SELECT payload_hash FROM interop_events WHERE event_id=$1',[event.eventId])).rows[0];if(old.payload_hash!==hash)throw interopError('Identifiant événement déjà utilisé avec un autre contenu.',409);return true;}
  await audit(c,'openfn','interop-'+event.status,{runId:event.runId,site:event.chw_site_id,period:event.period,mode:event.mode});return false;
 });
 return Response.json({ok:true,duplicate},{headers:{'Cache-Control':'no-store'}});
}catch(e){return apiError(e);}}
