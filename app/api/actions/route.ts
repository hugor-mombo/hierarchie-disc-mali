import {env} from 'cloudflare:workers';
import {fetchDHIS,fetchDISC} from '../../../lib/sources.mjs';
import {readState,saveSnapshot,approveMapping,removeMapping,putRecord,audit,getRecord,importMappings} from '../../../lib/state';
import {TYPES} from '../../../lib/reconcile.mjs';
export const dynamic='force-dynamic';
// This application is owner-private. Sites authenticates all page and API requests.
// Prevent cross-origin writes; database records never include platform credentials.
export async function POST(request:Request){
  const origin=request.headers.get('origin');if((origin&&origin!==new URL(request.url).origin)||request.headers.get('sec-fetch-site')==='cross-site')return Response.json({error:'Origine refusée.'},{status:403});
  const actor=request.headers.get('oai-authenticated-user-email')||'Accès privé';
  try{const b:any=await request.json();
    if(b.action==='refresh'){
      const result=await Promise.allSettled([fetchDISC(env),fetchDHIS(env)]);
      const failure=result.find(r=>r.status==='rejected');if(failure?.status==='rejected')throw failure.reason;
      const disc=(result[0]as PromiseFulfilledResult<any>).value,dhis=(result[1]as PromiseFulfilledResult<any>).value;
      await saveSnapshot(disc,dhis.nodes,dhis.levels,actor);
    }else if(b.action==='approve'){
      if(typeof b.discId!=='string'||typeof b.dhisId!=='string')throw Error('Identifiants requis.');
      await approveMapping(b.discId,b.dhisId,actor);
    }else if(b.action==='import'){
      await importMappings(b.mappings,actor);
    }else if(b.action==='remove'){
      if(typeof b.discId!=='string')throw Error('Identifiant requis.');await removeMapping(b.discId,actor);
    }else if(b.action==='levels'){
      const levels:any={};for(const[type]of TYPES){const v=b.levels?.[type];if(v!==null&&(!Number.isInteger(v)||v<1||v>8))throw Error('Niveau DHIS2 invalide.');levels[type]=v;}
      await putRecord('levels',levels);await audit(actor,'levels',levels);
    }else if(b.action==='name-plan'){
      if(!['disc','dhis'].includes(b.target)||typeof b.id!=='string'||typeof b.name!=='string'||b.name.trim().length<2||b.name.length>230)throw Error('Correction de nom invalide.');
      const state=await readState(),node=state.snapshot?.[b.target]?.find((n:any)=>n.id===b.id);if(!node)throw Error('Unité absente du relevé.');
      const plans=await getRecord('name-plans')||[];const plan={id:crypto.randomUUID(),target:b.target,unitId:b.id,expectedName:node.name,newName:b.name.trim(),createdAt:new Date().toISOString(),actor};
      await putRecord('name-plans',[...plans,plan].slice(-1000));await audit(actor,'name-plan',plan);
    }else throw Error('Action inconnue.');
    return Response.json(await readState(),{headers:{'Cache-Control':'no-store'}});
  }catch(e){const message=e instanceof Error?e.message:'Opération impossible.';return Response.json({error:message.includes('constraint')?'Cette unité est déjà rapprochée.':message.slice(0,240)},{status:400});}
}
