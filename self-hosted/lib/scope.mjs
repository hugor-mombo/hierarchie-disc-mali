export const DISTRICT_GROUP='EQgJEq5Ga2K';
export const CSCOM_GROUP='a8PnG1kmKY9';
export const ASC_GROUP='JBThfLOBPmn';
export function relevantDhis(node){
  if([1,2].includes(node.level))return true;
  if(node.level===3)return node.groups?.includes(DISTRICT_GROUP)===true;
  return node.level===5?node.groups?.includes(CSCOM_GROUP)===true:node.level===6&&node.groups?.includes(ASC_GROUP)===true;
}
// Closure is effective on the calendar date recorded by DHIS2, not before.
export function siteClosure(node,today=new Date().toISOString().slice(0,10)){
 if(node.level!==6||!Object.hasOwn(node,'closedDate'))return 'unknown';
 if(node.closedDate===null||node.closedDate==='')return 'open';
 if(typeof node.closedDate!=='string')return 'unknown';
 const day=node.closedDate.slice(0,10),date=new Date(day+'T00:00:00Z');
 if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==day)return 'unknown';
 return day<=today?'closed':'open';
}
export function siteStatus(node,today=new Date().toISOString().slice(0,10)){
 if(node.level!==6)return '';
 const status=siteClosure(node,today);
 if(status==='unknown')return 'Statut non relevé ou date invalide';
 if(node.closedDate){const date=node.closedDate.slice(0,10);return status==='closed'?'Fermé depuis le '+date:'Fermeture prévue le '+date;}
 return 'Ouvert';
}
