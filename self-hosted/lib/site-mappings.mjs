import {ASC_GROUP} from './scope.mjs';
import {indexNodes,pathOf} from './reconcile.mjs';
import {csv} from './exports.mjs';
// Only explicit or automatic registry mappings are exported. Never infer links
// from a proposal score when preparing an interoperability file.
export function siteMappingReport(snapshot,mappings=[]){
 if(!snapshot)throw Error('Charger les relevés avant l’export.');
 if((snapshot.dhis||[]).some(n=>n.level===6&&!Array.isArray(n.groups)))throw Error('Actualiser les relevés pour charger le groupe Sites ASC avant export.');
 const di=indexNodes(snapshot.disc||[]),hi=indexNodes(snapshot.dhis||[]),rows=[],excluded=[];
 const usedDisc=new Set(),usedDhis=new Set();
 for(const m of mappings){
  if(usedDisc.has(m.discId)||usedDhis.has(m.dhisId))throw Error('Correspondance dupliquée : corriger le registre avant export.');
  usedDisc.add(m.discId);usedDhis.add(m.dhisId);
  const d=di.get(m.discId),h=hi.get(m.dhisId);
  if(d?.type!=='c60_chw_site'){if(h?.level===6&&h.groups?.includes(ASC_GROUP))excluded.push({discId:m.discId,dhisId:m.dhisId,reason:'Contact DISC absent ou de type différent de Site ASC.'});continue;}
  if(!h||h.level!==6||!h.groups?.includes(ASC_GROUP)){excluded.push({discId:m.discId,dhisId:m.dhisId,reason:'UO DHIS2 absente, de niveau différent ou hors du groupe Sites ASC.'});continue;}
  rows.push({discId:d.id,dhisId:h.id,discName:d.name,dhisName:h.name,discPath:pathOf(d,di),dhisPath:pathOf(h,hi),method:m.method||'manual'});
 }
 rows.sort((a,b)=>a.discId.localeCompare(b.discId));
 const discCount=[...di.values()].filter(n=>n.type==='c60_chw_site').length,dhisCount=[...hi.values()].filter(n=>n.level===6&&n.groups?.includes(ASC_GROUP)).length;
 return {rows,excluded,discCount,dhisCount,discUnlinked:discCount-rows.length,dhisUnlinked:dhisCount-rows.length};
}
export function siteMappingCSV(snapshot,mappings=[]){
 const report=siteMappingReport(snapshot,mappings);
 return csv([['chw_site_id','dhis2_org_unit','active'],...report.rows.map(r=>[r.discId,r.dhisId,true])]);
}
