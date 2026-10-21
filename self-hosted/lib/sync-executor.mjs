import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {randomInt} from 'node:crypto';
import {planSync,assertSamePlan} from './sync-plan.mjs';
import {sourceURL,fetchDISC,fetchDHIS} from './sources.mjs';
import {assertWritesEnabled,remote,prepareMove,executeMove} from './move-executor.mjs';
import {CSCOM_GROUP,ASC_GROUP} from './scope.mjs';

export async function checkedResponse(response){
  if(response.status===204)return {};
  const text=await response.text();if(!text)return {};
  let data;try{data=JSON.parse(text);}catch{throw Error('Réponse distante non vérifiable.');}
  if(data.error||data.status==='ERROR'||data.response?.status==='ERROR'||data.response?.errorReports?.length||data.response?.stats?.ignored>0)throw Error('La plateforme a signalé un échec de validation.');
  return data;
}
async function preserve(row,env,name,value){
  if(!/^[a-f0-9-]{36}$/.test(row.id))throw Error('Identifiant invalide.');
  const dir=path.join(env.WORK_DIRECTORY||'/var/lib/hierarchie',row.id);
  await mkdir(dir,{recursive:true,mode:0o700});
  await writeFile(path.join(dir,name+'.json'),JSON.stringify(value),{mode:0o600});
}
export async function executeSync(row,env,mappings,currentLevels,onWrite=()=>{},authorize=async()=>{}){
  assertWritesEnabled(env);
  const {endpoints,...saved}=row.plan;
  for(const source of ['disc','dhis'])if(sourceURL(env,source)!==endpoints[source])throw Error('Une URL de plateforme a changé. Recréer l’action.');
  const [disc,dhis]=await Promise.all([fetchDISC(env),fetchDHIS(env)]);
  const snapshot={disc,dhis:dhis.nodes};
  const actual=planSync(snapshot,mappings,currentLevels||undefined,{originSource:row.origin_source,originId:row.origin_id,operation:row.operation,parentId:saved.parent?.id});
  assertSamePlan(saved,actual);
  await preserve(row,env,'action',row.plan);
  const p=row.plan,source=row.target_source;
  let targetId=p.target?.id;
  if(row.operation==='move'){
    const move={id:row.id,source,endpoint:endpoints[source],unit_id:targetId,new_parent_id:p.parent.id,expected_parent_id:p.target.parent,before_path:p.beforePath,after_path:p.afterPath,impact_count:p.impactCount};
    move.prepared_plan=await prepareMove(move,env);
    await preserve(row,env,'move-plan',move.prepared_plan);
    await authorize();
    return {...await executeMove(move,env,onWrite),targetId};
  }
  if(source==='disc'){
    if(row.operation==='create'){
      const settings=await (await remote('disc','/medic/settings',env)).json();
      const config=settings.settings?.contact_types?.find(t=>t.id===p.type);
      if(!config||config.person||!config.parents?.includes(p.parent.type))throw Error('Le type ou le parent n’est pas autorisé par la configuration DISC.');
      // The CHT place API validates and builds the full parent lineage. No person
      // or technical user is fabricated from organisation unit metadata.
      const body={name:p.origin.name,type:'contact',contact_type:p.type,parent:p.parent.id,dhis2_org_unit:p.origin.id};
      await authorize();onWrite();const result=await checkedResponse(await remote('disc','/api/v1/places',env,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}));
      targetId=result.id||result._id;await preserve(row,env,'create-result',result);if(typeof targetId!=='string'||!targetId)throw Error('Identifiant de la structure créée non retourné. Contrôle manuel requis.');
    }else{
      const doc=await (await remote('disc','/medic/'+encodeURIComponent(targetId),env)).json();
      if(doc._deleted||!doc._rev||doc.name!==p.target.name||doc.contact_type!==p.type||doc.parent?._id!==p.target.parent)throw Error('La structure DISC a changé.');
      await preserve(row,env,'before',doc);
      await authorize();onWrite();await checkedResponse(await remote('disc','/medic/'+encodeURIComponent(targetId),env,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...doc,name:p.origin.name})}));
    }
    const after=await (await remote('disc','/medic/'+encodeURIComponent(targetId),env)).json();
    if(after.name!==p.origin.name||after.parent?._id!==(p.parent?.id||p.target?.parent)||after.contact_type!==p.type||after._deleted)throw Error('La structure DISC ne correspond pas au résultat attendu.');
  }else{
    if(row.operation==='create'){
      // A generated UID is kept in the result; ambiguous writes are never retried.
      const letters='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',chars=letters+'0123456789';
      targetId=letters[randomInt(letters.length)]+Array.from({length:10},()=>chars[randomInt(chars.length)]).join('');
      const group=p.type==='c60_chw_site'?ASC_GROUP:p.type==='c40_health_area'?CSCOM_GROUP:null;
      const body={id:targetId,name:p.origin.name,shortName:p.origin.name.slice(0,50),openingDate:new Date().toISOString().slice(0,10),parent:{id:p.parent.id}};
      await preserve(row,env,'create-payload',{...body,group});
      await authorize();onWrite();await checkedResponse(await remote('dhis','/api/organisationUnits',env,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}));
      if(group){
        await authorize();
        await checkedResponse(await remote('dhis','/api/organisationUnitGroups/'+group,env,{method:'PATCH',headers:{'Content-Type':'application/json-patch+json'},body:JSON.stringify([{op:'add',path:'/organisationUnits/-',value:{id:targetId}}])}));
        const g=await (await remote('dhis','/api/organisationUnitGroups/'+group+'.json?fields=id,organisationUnits[id]',env)).json();
        if(!g.organisationUnits?.some(n=>n.id===targetId))throw Error('L’appartenance au groupe DHIS2 n’est pas vérifiée.');
      }
    }else{
      const response=await remote('dhis','/api/organisationUnits/'+encodeURIComponent(targetId)+'.json?fields=id,name,shortName,parent[id],lastUpdated',env),doc=await response.json();
      if(doc.name!==p.target.name||doc.parent?.id!==p.target.parent)throw Error('L’unité DHIS2 a changé.');
      await preserve(row,env,'before',doc);
      const patch=[{op:'test',path:'/name',value:p.target.name},{op:'replace',path:'/name',value:p.origin.name},{op:'add',path:'/shortName',value:p.origin.name.slice(0,50)}];
      await authorize();onWrite();await checkedResponse(await remote('dhis','/api/organisationUnits/'+encodeURIComponent(targetId),env,{method:'PATCH',headers:{'Content-Type':'application/json-patch+json',...(response.headers.get('etag')?{'If-Match':response.headers.get('etag')}:{})},body:JSON.stringify(patch)}));
    }
    const after=await (await remote('dhis','/api/organisationUnits/'+encodeURIComponent(targetId)+'.json?fields=id,name,level,parent[id]',env)).json();
    if(after.name!==p.origin.name||after.parent?.id!==(p.parent?.id||p.target?.parent)||after.level!==p.levels[p.type])throw Error('L’unité DHIS2 ne correspond pas au résultat attendu.');
  }
  return {targetId,verifiedAt:new Date().toISOString(),documents:1};
}
