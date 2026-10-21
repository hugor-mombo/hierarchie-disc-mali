import {TYPES} from './reconcile.mjs';
export async function remoteJSON(url,user,password,fetcher=fetch){
  const response=await fetcher(url,{headers:{Authorization:'Basic '+btoa(user+':'+password),Accept:'application/json'},redirect:'manual',signal:AbortSignal.timeout(90000)});
  if(!response.ok)throw Error(`Lecture ${new URL(url).hostname} : HTTP ${response.status}. Vérifier les accès et le service.`);
  return response.json();
}
export async function fetchDHIS(env,fetcher=fetch){
  if(!env.DHIS_USER||!env.DHIS_PASSWORD)throw Error('Accès DHIS2 non configuré sur le serveur.');
  const base=sourceURL(env,'dhis')+'/api/';
  const levels=await remoteJSON(base+'organisationUnitLevels.json?fields=id,name,level&paging=false',env.DHIS_USER,env.DHIS_PASSWORD,fetcher);
  let page=1,count=1;const nodes=new Map();
  do{const q=new URLSearchParams({fields:'id,name,code,level,path,parent[id]',page:String(page),pageSize:'1000',paging:'true',order:'id:asc'});const data=await remoteJSON(base+'organisationUnits.json?'+q,env.DHIS_USER,env.DHIS_PASSWORD,fetcher);if(!Array.isArray(data.organisationUnits)||!data.pager)throw Error('Réponse DHIS2 incomplète, relevé non remplacé.');for(const n of data.organisationUnits)nodes.set(n.id,{id:n.id,name:n.name,code:n.code||'',level:n.level,parent:n.parent?.id||null,path:n.path||''});count=data.pager.pageCount||Math.ceil(data.pager.total/1000)||1;if(page>1000)throw Error('Pagination DHIS2 excessive.');page++;}while(page<=count);
  return{nodes:[...nodes.values()],levels:levels.organisationUnitLevels||[]};
}
export async function fetchDISC(env,fetcher=fetch){
  if(!env.DISC_USER||!env.DISC_PASSWORD)throw Error('Accès DISC non configuré sur le serveur.');
  const base=sourceURL(env,'disc')+'/medic/_design/medic-client/_view/contacts_by_type';const nodes=new Map();
  // Keys verified against the production view: ["c60_chw_site"], not a string.
  for(const [type]of TYPES){let cursor=null,pages=0;while(true){const q=new URLSearchParams({include_docs:'true',reduce:'false',startkey:JSON.stringify([type]),endkey:JSON.stringify([type]),limit:'1000'});if(cursor){q.set('startkey_docid',cursor);q.set('skip','1');}const data=await remoteJSON(base+'?'+q,env.DISC_USER,env.DISC_PASSWORD,fetcher);if(!Array.isArray(data.rows))throw Error('Réponse DISC incomplète, relevé non remplacé.');for(const row of data.rows){const d=row.doc;if(!d||d.contact_type!==type)throw Error('Document DISC incomplet ou mauvais type.');nodes.set(d._id,{id:d._id,name:d.name||'(sans nom)',type:d.contact_type,parent:d.parent?._id||null,code:d.code||'',dhisId:d.dhis2_id||d.dhis2_org_unit||null});}if(data.rows.length<1000)break;const next=data.rows.at(-1).id;if(cursor===next||++pages>100)throw Error('Pagination DISC bloquée.');cursor=next;}}
  return [...nodes.values()];
}

export function sourceURL(env,source){const raw=source==='disc'?env.DISC_URL||'https://disc-mali.ml':env.DHIS_URL||'https://dhis2.snissmali.ml/dhis';const u=new URL(raw);if(u.username||u.password||u.search||u.hash||!['https:','http:'].includes(u.protocol))throw Error('URL source invalide.');if(u.protocol!=='https:'&&env.ALLOW_HTTP_SOURCES!=='true')throw Error('HTTPS requis pour les plateformes sources.');return u.toString().replace(/\/$/,'');}
