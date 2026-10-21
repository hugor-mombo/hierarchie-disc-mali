import {indexNodes,ancestors,pathOf,TYPES} from './reconcile.mjs';
export const DELETION_STATUS={prepare_queued:'Préparation en attente',preparing:'Calcul du périmètre',prepared:'Plan à confirmer',queued:'Suppression en attente',executing:'Suppression en cours',succeeded:'Suppression vérifiée',failed:'Arrêt avant suppression',uncertain:'Contrôle manuel requis',cancelled:'Annulée'};
export function planDeletion(snapshot,mappings,unitId){
 const nodes=snapshot?.disc||[],index=indexNodes(nodes),root=index.get(unitId);
 if(!root)throw Error('Unité DISC absente du relevé.');
 if(!TYPES.some(([type])=>type===root.type))throw Error('Type de structure non pris en charge.');
 if(!root.parent||root.type==='c10_central')throw Error('La racine DISC ne peut pas être supprimée.');
 const chain=[root,...ancestors(root,index)];if(chain.at(-1).parent||new Set(chain.map(n=>n.id)).size!==chain.length)throw Error('Hiérarchie incomplète ou cyclique.');
 const branch=nodes.filter(n=>n.id===root.id||ancestors(n,index).some(a=>a.id===root.id));
 const ids=new Set(branch.map(n=>n.id)),dhisIds=new Set((snapshot.dhis||[]).map(n=>n.id));
 if(mappings.some(m=>ids.has(m.discId))||branch.some(n=>n.dhisId&&dhisIds.has(n.dhisId)))throw Error('Une unité de cette branche possède une correspondance DHIS2. Vérifier et résoudre ces liens avant toute suppression.');
 return {unitId:root.id,name:root.name,path:pathOf(root,index),units:branch.map(n=>({id:n.id,name:n.name,parent:n.parent,type:n.type})).sort((a,b)=>a.id.localeCompare(b.id))};
}
export function assertDeletionConfirmation(row,b,writesEnabled){
 if(row.status!=='prepared'||!row.prepared_plan?.hash)throw Error('Un plan préparé doit être relu avant exécution.');
 if(!writesEnabled)throw Error('Les écritures distantes sont désactivées.');
 if(b.planHash!==row.prepared_plan.hash||b.confirmName!==row.unit_name||b.confirmed!==true||b.backupConfirmed!==true||b.dataConfirmed!==true)throw Error('Confirmer le plan, son nom exact, les contacts, les rapports et la sauvegarde.');
 const age=Date.now()-Date.parse(row.prepared_plan.preparedAt);if(!Number.isFinite(age)||age<0||age>3600000)throw Error('Plan expiré : annuler puis préparer une nouvelle demande.');
}
export function deletionDocSummary(docs,settings,scope){
 const types=new Map((settings?.settings?.contact_types||[]).map(t=>[t.id,t]));
 if(!types.size)throw Error('Types de contacts DISC non disponibles.');
 const ids=new Set(docs.map(d=>d._id));if(!ids.has(scope.unitId))throw Error('Le plan CHT ne contient pas l’unité choisie.');
 const contactIds=new Set(docs.filter(x=>x.type!=='data_record').map(x=>x._id));
 const structural=new Set(scope.units.map(n=>n.id));let places=0,people=0,reports=0;
 const documents=docs.map(d=>{
  if(!d._id||!d._rev||d._deleted)throw Error('Document absent, supprimé ou sans révision.');
  if(d.type==='data_record'){const contacts=contactIds;let creator=d.contact;const seen=new Set();let related=false;while(creator&&!seen.has(creator._id)){seen.add(creator._id);if(contacts.has(creator._id))related=true;creator=creator.parent;}if(!related&&!['patient_id','patient_uuid','place_id','place_uuid'].some(k=>contacts.has(d[k])||contacts.has(d.fields?.[k])))throw Error('Rapport hors de la branche choisie.');reports++;return {id:d._id,kind:'report',name:'Rapport',revision:d._rev};}
  const type=types.get(d.type==='contact'?d.contact_type:d.type);if(!type)throw Error('Type de document inconnu : contrôle manuel requis.');
  const seen=new Set();let p=d;while(p&&p._id!==scope.unitId){if(seen.has(p._id))throw Error('Lignage cyclique.');seen.add(p._id);p=p.parent;}
  if(!p)throw Error('Contact hors de la branche choisie.');
  if(type.person)people++;else{places++;if(!structural.has(d._id))throw Error('Structure absente du relevé : actualiser avant suppression.');}
  return {id:d._id,kind:type.person?'person':'place',name:type.person?'Personne':d.name||'(sans nom)',revision:d._rev};
 }).sort((a,b)=>a.id.localeCompare(b.id));
 if(structural.size!==places)throw Error('Le périmètre CHT diffère de la branche du relevé.');
 return {places,people,reports,documents};
}
