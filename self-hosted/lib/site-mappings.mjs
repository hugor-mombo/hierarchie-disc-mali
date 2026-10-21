import {ASC_GROUP,siteClosure} from './scope.mjs';
import {indexNodes,pathOf,ancestors} from './reconcile.mjs';
import {csv} from './exports.mjs';
// Only explicit or automatic registry mappings are exported. Never infer links
// from a proposal score when preparing an interoperability file.
export function dhisSiteCounts(snapshot,today=new Date().toISOString().slice(0,10)){
 const sites=(snapshot?.dhis||[]).filter(n=>n.level===6&&n.groups?.includes(ASC_GROUP));
 const counts={total:sites.length,open:0,closed:0,unknown:0,scheduled:0};
 for(const n of sites){const status=siteClosure(n,today);counts[status]++;if(status==='open'&&n.closedDate)counts.scheduled++;}
 return counts;
}
function branchFields(node,index,source){
 const branch=[node,...ancestors(node,index)],find=value=>source==='disc'?branch.find(n=>n.type===value):branch.find(n=>n.level===value);
 const region=find(source==='disc'?'c20_region':2),district=find(source==='disc'?'c30_district':3),cscom=find(source==='disc'?'c40_health_area':5),intermediate=find(source==='disc'?'c50_supervision_area':4);
 return {region:region?.name||'',regionId:region?.id||'',district:district?.name||'',districtId:district?.id||'',cscom:cscom?.name||'',cscomId:cscom?.id||'',intermediate:intermediate?.name||'',intermediateId:intermediate?.id||''};
}
export function siteMappingReport(snapshot,mappings=[],today=new Date().toISOString().slice(0,10)){
 if(!snapshot)throw Error('Charger les relevés avant l’export.');
 if((snapshot.dhis||[]).some(n=>n.level===6&&!Array.isArray(n.groups)))throw Error('Actualiser les relevés pour charger le groupe Sites ASC avant export.');
 const di=indexNodes(snapshot.disc||[]),hi=indexNodes(snapshot.dhis||[]),rows=[],excluded=[];
 const usedDisc=new Set(),usedDhis=new Set(),linkedDisc=new Set(),linkedDhis=new Set();
 for(const m of mappings){
  if(usedDisc.has(m.discId)||usedDhis.has(m.dhisId))throw Error('Correspondance dupliquée : corriger le registre avant export.');
  usedDisc.add(m.discId);usedDhis.add(m.dhisId);
  const d=di.get(m.discId),h=hi.get(m.dhisId);
  if(d?.type!=='c60_chw_site'){if(h?.level===6&&h.groups?.includes(ASC_GROUP))excluded.push({discId:m.discId,dhisId:m.dhisId,reason:'Contact DISC absent ou de type différent de Site ASC.'});continue;}
  if(!h||h.level!==6||!h.groups?.includes(ASC_GROUP)){excluded.push({discId:m.discId,dhisId:m.dhisId,reason:'UO DHIS2 absente, de niveau différent ou hors du groupe Sites ASC.'});continue;}
  linkedDisc.add(d.id);linkedDhis.add(h.id);
  const status=siteClosure(h,today);
  if(status!=='open'){excluded.push({discId:m.discId,dhisId:m.dhisId,category:status,reason:status==='closed'?'Site fermé dans DHIS2 depuis le '+h.closedDate.slice(0,10)+'.':'Statut de fermeture DHIS2 inconnu ou invalide : actualiser avant export.'});continue;}
  rows.push({discBranch:branchFields(d,di,'disc'),dhisBranch:branchFields(h,hi,'dhis'),scheduledClosure:h.closedDate?h.closedDate.slice(0,10):'',discId:d.id,dhisId:h.id,discName:d.name,dhisName:h.name,discPath:pathOf(d,di),dhisPath:pathOf(h,hi),method:m.method||'manual'});
 }
 rows.sort((a,b)=>a.discId.localeCompare(b.discId));
 const discCount=[...di.values()].filter(n=>n.type==='c60_chw_site').length,dhisCount=[...hi.values()].filter(n=>n.level===6&&n.groups?.includes(ASC_GROUP)).length;
 const dhisSites=dhisSiteCounts(snapshot,today);
 return {rows,excluded,discCount,dhisCount,dhisSites,discUnlinked:discCount-linkedDisc.size,dhisUnlinked:dhisCount-linkedDhis.size,dhisOpenUnlinked:dhisSites.open-rows.length};
}
export const SITE_MAPPING_HEADERS=['chw_site_id','dhis2_org_unit','active','site_disc','site_dhis2','region_disc','district_disc','cscom_disc','zone_supervision_disc','region_dhis2','district_dhis2','aire_sante_dhis2','cscom_dhis2','chemin_disc','chemin_dhis2','region_disc_id','district_disc_id','cscom_disc_id','zone_supervision_disc_id','region_dhis2_id','district_dhis2_id','aire_sante_dhis2_id','cscom_dhis2_id','statut_dhis2','fermeture_prevue_dhis2'];
export function siteMappingCSV(snapshot,mappings=[],today=new Date().toISOString().slice(0,10)){
 const report=siteMappingReport(snapshot,mappings,today);
 return csv([SITE_MAPPING_HEADERS,...report.rows.map(r=>[r.discId,r.dhisId,true,r.discName,r.dhisName,r.discBranch.region,r.discBranch.district,r.discBranch.cscom,r.discBranch.intermediate,r.dhisBranch.region,r.dhisBranch.district,r.dhisBranch.intermediate,r.dhisBranch.cscom,r.discPath,r.dhisPath,r.discBranch.regionId,r.discBranch.districtId,r.discBranch.cscomId,r.discBranch.intermediateId,r.dhisBranch.regionId,r.dhisBranch.districtId,r.dhisBranch.intermediateId,r.dhisBranch.cscomId,'Ouvert',r.scheduledClosure])]);
}
