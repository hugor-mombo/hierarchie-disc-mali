export const TYPES = [
  ['c10_central','Central'],['c20_region','Région'],['c30_district','District'],
  ['c40_health_area','Aire de santé'],['c50_supervision_area','Zone de supervision'],['c60_chw_site','Site ASC'],
];
export const DEFAULT_LEVELS={c10_central:1,c20_region:2,c30_district:3,c40_health_area:5,c50_supervision_area:null,c60_chw_site:6};
export const STATUS={aligned:'Concordant',name:'Nom différent',parent:'Hiérarchie différente',level:'Niveau différent',proposal:'À rapprocher',ambiguous:'Correspondance ambiguë',missing:'Sans correspondance',dhis:'DHIS2 non rapproché',broken:'Mapping invalide',skipped:'Niveau non comparé'};
export function normalize(value){
  return String(value||'').toLowerCase().replaceAll('œ','oe').replaceAll('æ','ae')
    .normalize('NFD').replace(/[\u0300-\u036f]/g,'')
    .replace(/\b(district\s+sanitaire|aire\s+de\s+sante|zone\s+de\s+supervision|site\s+asc|districts?|region|cscom|csref)\b/g,' ')
    .replace(/\b(de|du|des|la|le)\b/g,' ').replace(/[^a-z0-9]+/g,' ').trim().replace(/\s+/g,' ');
}
export function matchingName(value){return normalize(String(value||'').replace(/[’'`]/g,''));}
export function indexNodes(nodes){return new Map(nodes.map(n=>[n.id,n]));}
export function ancestors(node,index){const a=[];const seen=new Set([node.id]);let p=node.parent;while(p&&index.has(p)&&!seen.has(p)){seen.add(p);const n=index.get(p);a.push(n);p=n.parent;}return a;}
export function pathOf(node,index){return [...ancestors(node,index)].reverse().concat(node).map(n=>n.name).join(' / ');}
function dice(a,b){a=normalize(a).replaceAll(' ','');b=normalize(b).replaceAll(' ','');if(a===b)return a?1:0;if(a.length<2||b.length<2)return 0;const p=new Map();for(let i=0;i<a.length-1;i++){const k=a.slice(i,i+2);p.set(k,(p.get(k)||0)+1);}let overlap=0;for(let i=0;i<b.length-1;i++){const k=b.slice(i,i+2);if(p.get(k)>0){overlap++;p.set(k,p.get(k)-1);}}return 2*overlap/(a.length+b.length-2);}
function compareRows(snapshot,mappings=[],levels=DEFAULT_LEVELS,dhisFilter=()=>true){
  const disc=snapshot.disc||[],dhis=snapshot.dhis||[],di=indexNodes(disc),hi=indexNodes(dhis);
  const provenance=new Map(mappings.map(m=>[m.discId,m]));const confirmed=new Map(mappings.map(m=>[m.discId,m.dhisId]));const used=new Set(mappings.map(m=>m.dhisId));
  const byLevel=new Map(),byName=new Map(),byDistrict=new Map();
  for(const h of dhis.filter(dhisFilter)){if(!byLevel.has(h.level))byLevel.set(h.level,[]);byLevel.get(h.level).push(h);const key=h.level+'|'+normalize(h.name);if(!byName.has(key))byName.set(key,[]);byName.get(key).push(h);const district=ancestors(h,hi).find(p=>p.level===3);const dk=h.level+'|'+normalize(district?.name||'');if(!byDistrict.has(dk))byDistrict.set(dk,[]);byDistrict.get(dk).push(h);}
  const rows=[];
  for(const d of disc){
    const da=ancestors(d,di),region=da.find(p=>p.type==='c20_region')|| (d.type==='c20_region'?d:null),district=da.find(p=>p.type==='c30_district')||(d.type==='c30_district'?d:null);
    const level=levels[d.type]; const target=confirmed.get(d.id),h=target?hi.get(target):null;
    const base={id:d.id,mappingMethod:provenance.get(d.id)?.method||'manual',matchBasis:provenance.get(d.id)?.matchBasis||null,disc:d,dhis:h||null,region:region?.name||'',regionId:region?.id||'',district:district?.name||'',districtId:district?.id||'',discPath:pathOf(d,di),dhisPath:h?pathOf(h,hi):'',candidates:[],reason:''};
    if(target&&!h){rows.push({...base,status:'broken',reason:'L’identifiant DHIS2 validé est absent du dernier relevé.'});continue;}
    if(h){
      let status='aligned',reason=provenance.get(d.id)?.method==='automatic'?'Correspondance automatique unique : niveau et branche vérifiés.':'Correspondance validée.';
      const nearest=da.find(p=>confirmed.has(p.id));
      if(level!=null&&h.level!==Number(level)){status='level';reason='Le niveau DHIS2 ne correspond pas au niveau configuré.';}
      else if(nearest&&!ancestors(h,hi).some(p=>p.id===confirmed.get(nearest.id))){status='parent';reason='L’ancêtre DISC rapproché ne figure pas dans la branche DHIS2.';}
      else if(matchingName(d.name)!==matchingName(h.name)){status='name';reason='Les libellés des deux unités sont différents.';}
      else if(d.name.trim()!==h.name.trim())reason+=' Libellés équivalents après normalisation de la casse, des accents et des préfixes.';
      if(!nearest&&da.length)reason+=' Parents non encore validés : contrôle de branche incomplet.';
      rows.push({...base,status,reason});continue;
    }
    if(level==null){rows.push({...base,status:'skipped',reason:'Choisir un niveau DHIS2 pour comparer ce type de structure.'});continue;}
    const exact=(byName.get(Number(level)+'|'+normalize(d.name))||[]).filter(x=>!used.has(x.id));
    const districtPool=byDistrict.get(Number(level)+'|'+normalize(district?.name||''))||[];
    const pool=exact.length?exact:(districtPool.length?districtPool:(byLevel.get(Number(level))||[]));
    const nearest=da.find(p=>confirmed.has(p.id));
    const candidates=pool.filter(x=>!used.has(x.id)).map(x=>{
      const hd=ancestors(x,hi).find(p=>p.level===3),sameDistrict=!!district&&normalize(hd?.name)===normalize(district.name);
      const branch=nearest?ancestors(x,hi).some(p=>p.id===confirmed.get(nearest.id)):false;
      return {id:x.id,name:x.name,path:pathOf(x,hi),score:Math.round(100*(dice(d.name,x.name)*0.78+(sameDistrict?0.12:0)+(branch?0.10:0))),sameDistrict,branch,exact:normalize(d.name)===normalize(x.name)};
    }).filter(c=>c.exact||c.score>=52).sort((a,b)=>b.score-a.score||a.id.localeCompare(b.id)).slice(0,5);
    const ambiguous=candidates.length>1&&(candidates[0].score-candidates[1].score<8);
    rows.push({...base,candidates,status:!candidates.length?'missing':ambiguous?'ambiguous':'proposal',reason:!candidates.length?'Aucune proposition fiable dans le périmètre chargé.':ambiguous?'Plusieurs unités proches : vérifier les parents avant de valider.':'Proposition indicative, à valider par une personne.'});
  }
  for(const h of dhis.filter(dhisFilter)){const hr=[h,...ancestors(h,hi)].find(n=>n.level===2);const dr=hr?disc.find(n=>n.type==='c20_region'&&(confirmed.get(n.id)===hr.id||normalize(n.name)===normalize(hr.name))):null;if(!used.has(h.id))rows.push({id:'dhis:'+h.id,disc:null,dhis:h,status:'dhis',region:dr?.name||'',regionId:dr?.id||'',district:'',districtId:'',discPath:'',dhisPath:pathOf(h,hi),candidates:[],reason:'Aucun mapping validé ne référence cette unité DHIS2. Cela ne prouve pas son absence de DISC.'});}
  for(const m of mappings){if(!di.has(m.discId))rows.push({id:'broken:'+m.discId,disc:null,dhis:hi.get(m.dhisId)||null,status:'broken',region:'',regionId:'',district:'',districtId:'',discPath:m.discId,dhisPath:m.dhisId,candidates:[],reason:'L’unité DISC validée est absente du dernier relevé.'});}
  return rows;
}
// Presence is an assessment of the loaded snapshot, never proof of absence.
export function compare(snapshot,mappings=[],levels=DEFAULT_LEVELS,dhisFilter=()=>true){
  const rows=compareRows(snapshot,mappings,levels,dhisFilter),di=indexNodes(snapshot.disc||[]),hi=indexNodes(snapshot.dhis||[]);
  const dm=new Map(mappings.map(m=>[m.discId,m.dhisId])),hm=new Map(mappings.map(m=>[m.dhisId,m.discId]));
  const discOptions=new Map(),dhisNames=new Set((snapshot.dhis||[]).map(h=>h.level+'|'+matchingName(h.name)));
  const addOption=(id,r)=>{if(!discOptions.has(id))discOptions.set(id,new Map());discOptions.get(id).set(r.disc.id,r);};
  const dhisByName=new Map();for(const h of snapshot.dhis||[]){const key=h.level+'|'+matchingName(h.name);if(!dhisByName.has(key))dhisByName.set(key,[]);dhisByName.get(key).push(h);}
  for(const r of rows.filter(r=>r.disc)){for(const c of r.candidates)addOption(c.id,r);for(const h of dhisByName.get(Number(levels[r.disc.type])+'|'+matchingName(r.disc.name))||[])addOption(h.id,r);}

  for(const row of rows){
    if(row.disc&&row.dhis){row.presence='linked';continue;}
    if(row.status==='broken'||row.status==='skipped'){row.presence='unverified';continue;}
    if(row.disc){
      const parent=ancestors(row.disc,di).find(n=>levels[n.type]!=null);
      const hasCandidate=row.candidates.length||dhisNames.has(Number(levels[row.disc.type])+'|'+matchingName(row.disc.name));
      row.presence=hasCandidate?'review':(!row.disc.parent||parent&&hi.has(dm.get(parent.id)))?'probable':'unverified';
      row.presenceReason=hasCandidate?'Des unités DHIS2 candidates existent : vérifier la correspondance avant de créer.':row.presence==='probable'?'Aucun candidat trouvé dans le relevé DHIS2 au niveau configuré. Vérifier avant toute création.':'Le parent DISC doit être rapproché avant de conclure sur cette unité.';
      continue;
    }
    if(row.dhis){
      const h=row.dhis;
      row.discCandidates=[...(discOptions.get(h.id)?.values()||[])].map(r=>({id:r.disc.id,name:r.disc.name,path:r.discPath,linked:dm.has(r.disc.id)}));
      const parent=ancestors(h,hi).find(n=>Object.values(levels).some(l=>l!=null&&Number(l)===n.level));
      row.presence=row.discCandidates.length?'review':(!h.parent||parent&&di.has(hm.get(parent.id)))?'probable':'unverified';
      row.presenceReason=row.discCandidates.length?'Un ou plusieurs contacts DISC peuvent correspondre. Vérifier leurs noms et leurs parents ; ne pas créer de doublon.':row.presence==='probable'?'Aucun candidat DISC trouvé au niveau correspondant dans le relevé chargé. Absence probable, à vérifier avant création.':'Le parent DHIS2 n’est pas encore rapproché : vérifier sa correspondance avant de conclure sur cette unité.';
    }
  }
  return rows;
}
export function presenceLabel(row){return row.presence==='linked'?'Présente dans les deux plateformes':row.presence==='review'?'Correspondance à vérifier':row.presence==='probable'?(row.disc?'Absence probable dans DHIS2':'Absence probable dans DISC'):'Parent ou périmètre à vérifier';}
export function changesSince(previous,current){
  if(!previous)return [];
  const changes=[];for(const source of ['disc','dhis']){const before=indexNodes(previous[source]||[]),after=indexNodes(current[source]||[]);for(const [id,n]of after){const old=before.get(id);if(!old)changes.push({source,id,name:n.name,kind:'Ajout'});else if(old.name!==n.name||old.parent!==n.parent)changes.push({source,id,name:n.name,kind:old.parent!==n.parent?'Déplacement':'Renommage',before:{name:old.name,parent:old.parent},after:{name:n.name,parent:n.parent}});}for(const [id,n]of before)if(!after.has(id))changes.push({source,id,name:n.name,kind:'Absent du relevé'});}return changes;
}
export function mappingCSV(mappings,snapshot){const di=indexNodes(snapshot.disc);const header=['discId','chw_site_id','dhis2_org_unit','active','supervisor_area_id','disc_contact_type','disc_name'];const quote=v=>'"'+(/^[\s]*[=+@-]/.test(String(v??''))?"'"+String(v??''):String(v??'')).replaceAll('"','""')+'"';return '\ufeff'+[header,...mappings.map(m=>{const d=di.get(m.discId);return[m.discId,d?.type==='c60_chw_site'?m.discId:'',m.dhisId,'true',d?.type==='c50_supervision_area'?m.discId:'',d?.type||'',d?.name||''];})].map(r=>r.map(quote).join(',')).join('\r\n');}
export function parseMappings(text){
  // JSON or RFC 4180 CSV, including quoted newlines and UTF-8 BOM.
  text=text.replace(/^\ufeff/,'').trim();let data;
  if(text.startsWith('[')||text.startsWith('{')){const parsed=JSON.parse(text);data=Array.isArray(parsed)?parsed:parsed.mappings;if(!Array.isArray(data))throw Error('Un tableau mappings est requis.');}
  else{const lines=[];let row=[],cell='',quoted=false;for(let i=0;i<text.length;i++){const ch=text[i];if(ch==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}else if(ch===','&&!quoted){row.push(cell);cell='';}else if((ch==='\n'||ch==='\r')&&!quoted){if(ch==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(Boolean))lines.push(row);row=[];cell='';}else cell+=ch;}if(quoted)throw Error('Guillemet CSV non fermé.');row.push(cell);if(row.some(Boolean))lines.push(row);const headers=lines.shift()||[];data=lines.map(values=>Object.fromEntries(headers.map((h,i)=>[h.trim(),values[i]?.trim()||''])));}
  const mappings=data.filter(r=>r.active===undefined||r.active===true||['true','1'].includes(String(r.active).toLowerCase())).map(r=>({discId:r.discId||r.chw_site_id||r.supervisor_area_id||r.site_chw_uuid||r.cscom_uuid,dhisId:r.dhisId||r.dhis2_org_unit||r.org_unit_id}));
  if(!mappings.length||mappings.some(m=>!m.discId||!m.dhisId))throw Error('Identifiants DISC et DHIS2 requis pour chaque ligne active.');
  if(new Set(mappings.map(m=>m.discId)).size!==mappings.length||new Set(mappings.map(m=>m.dhisId)).size!==mappings.length)throw Error('Le fichier contient des correspondances dupliquées.');return mappings;
}
export function treeOrder(nodes){const index=indexNodes(nodes),children=new Map();for(const n of nodes){const key=index.has(n.parent)?n.parent:null;if(!children.has(key))children.set(key,[]);children.get(key).push(n);}for(const list of children.values())list.sort((a,b)=>a.name.localeCompare(b.name,'fr'));const out=[],seen=new Set();function visit(n){if(seen.has(n.id))return;seen.add(n.id);out.push(n);for(const child of children.get(n.id)||[])visit(child);}for(const n of children.get(null)||[])visit(n);for(const n of nodes)visit(n);return out;}
