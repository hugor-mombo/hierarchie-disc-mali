export const CSCOM_GROUP='a8PnG1kmKY9';
export const ASC_GROUP='JBThfLOBPmn';
export function relevantDhis(node){
  if([1,2,3].includes(node.level))return true;
  return node.level===5?node.groups?.includes(CSCOM_GROUP)===true:node.level===6&&node.groups?.includes(ASC_GROUP)===true;
}
export function siteStatus(node,today=new Date().toISOString().slice(0,10)){
  if(node.level!==6)return '';
  if(node.closedDate){const date=node.closedDate.slice(0,10);return date<=today?'Fermé depuis le '+date:'Fermeture prévue le '+date;}
  return Object.hasOwn(node,'closedDate')?'Ouvert':'Statut non relevé';
}
