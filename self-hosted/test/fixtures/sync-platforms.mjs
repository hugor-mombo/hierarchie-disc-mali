import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {demoState} from '../../lib/demo.mjs';
import {planSync} from '../../lib/sync-plan.mjs';
import {CSCOM_GROUP,ASC_GROUP} from '../../lib/scope.mjs';
export async function fixture(work){
  const s=demoState(),docs=new Map(s.snapshot.disc.map(n=>[n.id,{_id:n.id,_rev:'1-qa',type:'contact',contact_type:n.type,name:n.name,parent:n.parent?{_id:n.parent}:undefined}]));
  const env={DISC_URL:'https://disc.example',DISC_USER:'qa',DISC_PASSWORD:'qa',DHIS_URL:'https://dhis.example/dhis',DHIS_USER:'qa',DHIS_PASSWORD:'qa',ENABLE_REMOTE_WRITES:'true',WORK_DIRECTORY:work};
  const writes=[],calls=[];let failAfterWrite=false;
  const fetcher=async(raw,options={})=>{
    const u=new URL(raw),method=options.method||'GET';calls.push(method+' '+u.pathname);
    const json=(d,status=200)=>new Response(JSON.stringify(d),{status,headers:{'Content-Type':'application/json'}});
    if(u.hostname==='disc.example'){
      if(u.pathname.endsWith('/contacts_by_type')){const type=JSON.parse(u.searchParams.get('startkey'))[0];return json({rows:[...docs.values()].filter(d=>d.contact_type===type).map(doc=>({id:doc._id,doc}))});}
      if(u.pathname==='/medic/settings')return json({settings:{contact_types:[{id:'c60_chw_site',parents:['c50_supervision_area']}]}});
      if(u.pathname==='/api/v1/places'&&method==='POST'){
        const b=JSON.parse(options.body);assert.equal(b.type,'contact');assert.equal(b.contact_type,'c60_chw_site');assert.equal(b.parent,'d4');assert.equal(b.contact,undefined);
        const id='created-qa';docs.set(id,{...b,_id:id,_rev:'1-new',parent:{_id:b.parent,parent:{_id:'d3'}}});writes.push('disc-create');return json({ok:true,id,rev:'1-new'});
      }
      const id=u.pathname.slice('/medic/'.length),doc=docs.get(id);
      if(!doc)return json({error:'not_found'},404);
      if(method==='PUT'){
        const b=JSON.parse(options.body);assert.equal(b._rev,doc._rev);assert.deepEqual(b.parent,doc.parent);docs.set(id,b);writes.push('disc-rename');return json({ok:true,id});
      }
      return json(doc);
    }
    if(u.pathname.endsWith('organisationUnitLevels.json'))return json({organisationUnitLevels:s.snapshot.dhisLevels});
    if(u.pathname.includes('/organisationUnitGroups/')){
      const id=u.pathname.split('/').at(-1).replace(/\.json$/,'');
      if(method==='PATCH'){const b=JSON.parse(options.body);const n=s.snapshot.dhis.find(n=>n.id===b[0].value.id);n.groups.push(id);writes.push('dhis-group');return json({status:'OK'});}
      return json({id,organisationUnits:s.snapshot.dhis.filter(n=>n.groups.includes(id)).map(n=>({id:n.id}))});
    }
    const dhisNode=n=>({...n,parent:n.parent?{id:n.parent}:undefined});
    if(u.pathname.endsWith('organisationUnits.json'))return json({pager:{pageCount:1},organisationUnits:s.snapshot.dhis.map(dhisNode)});
    if(u.pathname.endsWith('/organisationUnits')&&method==='POST'){
      const b=JSON.parse(options.body);assert.match(b.id,/^[a-zA-Z][a-zA-Z0-9]{10}$/);assert.equal(b.parent.id,'h4');
      s.snapshot.dhis.push({...b,level:6,parent:b.parent.id,groups:[],closedDate:null});writes.push('dhis-create');if(failAfterWrite)return json({error:'disconnected'},503);return json({status:'OK'});
    }
    const id=u.pathname.split('/').at(-1).replace(/\.json$/,''),n=s.snapshot.dhis.find(n=>n.id===id);
    if(!n)return json({},404);
    if(method==='PATCH'){
      const b=JSON.parse(options.body);assert.equal(b[0].op,'test');assert.equal(b[0].value,n.name);n.name=b[1].value;writes.push('dhis-rename');return json({status:'OK'});
    }
    return json(dhisNode(n));
  };
  function row(input){const p=planSync(s.snapshot,s.mappings,s.levels,input);p.endpoints={disc:env.DISC_URL,dhis:env.DHIS_URL};return{id:randomUUID(),origin_source:p.originSource,target_source:p.targetSource,origin_id:p.origin.id,operation:p.operation,plan:p};}
  return{s,env,writes,calls,fetcher,row,docs,fail:()=>{failAfterWrite=true;}};
}
