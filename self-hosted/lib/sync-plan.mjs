import {DEFAULT_LEVELS,indexNodes,ancestors,pathOf,normalize} from './reconcile.mjs';
import {DISC_PARENTS,validateMove} from './move-validation.mjs';
import {CSCOM_GROUP,ASC_GROUP} from './scope.mjs';

export const OPERATIONS={create:'Créer l’unité',rename:'Mettre à jour le nom',move:'Déplacer l’unité'};
export function otherSource(source){if(!['dhis','disc'].includes(source))throw Error('Référence invalide.');return source==='dhis'?'disc':'dhis';}
export function mappedId(mappings,source,id){const m=mappings.find(m=>source==='disc'?m.discId===id:m.dhisId===id);return m?(source==='disc'?m.dhisId:m.discId):null;}
export function targetType(origin,source,levels=DEFAULT_LEVELS){
  if(source==='disc')return origin.type;
  const types=Object.keys(levels).filter(type=>levels[type]===origin.level);return types.length===1?types[0]:'';
}
export function parentCandidates(snapshot,mappings,source,origin,type,levels=DEFAULT_LEVELS){
  const target=otherSource(source),index=indexNodes(snapshot[source]||[]),ti=indexNodes(snapshot[target]||[]);
  const ancestor=ancestors(origin,index).find(n=>mappedId(mappings,source,n.id));
  if(!ancestor)return [];
  const anchor=mappedId(mappings,source,ancestor.id);
  const level=levels[origin.type];
  return (snapshot[target]||[]).filter(n=>target==='disc'?({c20_region:['c10_central'],...DISC_PARENTS})[type]?.includes(n.type):Number.isInteger(level)&&n.level===level-1)
    .filter(n=>[n,...ancestors(n,ti)].some(a=>a.id===anchor));
}
export function structural(node){return node?{id:node.id,name:node.name,parent:node.parent||null,type:node.type||null,level:node.level||null,groups:[...(node.groups||[])].sort(),closedDate:node.closedDate||null}:null;}
export function planSync(snapshot,mappings,levels=DEFAULT_LEVELS,input){
  const source=input.originSource||'dhis',target=otherSource(source),origin=snapshot?.[source]?.find(n=>n.id===input.originId);
  if(!origin)throw Error('Unité de référence absente du relevé.');
  if(!Object.hasOwn(OPERATIONS,input.operation))throw Error('Opération inconnue.');
  const targetId=mappedId(mappings,source,origin.id),unit=snapshot[target].find(n=>n.id===targetId);
  const type=targetType(origin,source,levels);
  if(!type||type==='c50_supervision_area')throw Error('Configurer un niveau comparable pour cette structure.');
  if(source==='dhis'&&((origin.level===5&&!origin.groups?.includes(CSCOM_GROUP))||(origin.level===6&&!origin.groups?.includes(ASC_GROUP))))throw Error('Cette UO n’appartient pas au groupe CSCOM ou Sites ASC attendu.');
  if(input.operation==='create'&&targetId)throw Error('Une correspondance existe déjà.');
  if(input.operation!=='create'&&!unit)throw Error('Valider la correspondance avant de modifier une unité existante.');
  if(unit&&(target==='disc'?unit.type!==type:unit.level!==levels[origin.type]))throw Error('Les niveaux de la correspondance sont incompatibles.');
  let parent=null,move=null;
  if(input.operation!=='rename'){
    const candidates=parentCandidates(snapshot,mappings,source,origin,type,levels);
    parent=candidates.find(n=>n.id===input.parentId);
    if(!parent)throw Error('Choisir un parent compatible dans la branche d’un ancêtre rapproché de la référence.');
    if(input.operation==='create'){
      if(snapshot[target].some(n=>(n.parent===parent.id&&normalize(n.name)===normalize(origin.name))||(target==='disc'&&n.dhisId===origin.id)))throw Error('Une unité similaire ou déjà liée existe : vérifier et rapprocher avant de créer.');
    }else move=validateMove(snapshot,target,unit.id,parent.id);
  }
  if(input.operation==='rename'&&origin.name===unit.name)throw Error('Les noms sont déjà identiques.');
  if(typeof origin.name!=='string'||origin.name.trim().length<2||origin.name.length>230)throw Error('Nom de référence invalide.');
  return {originSource:source,targetSource:target,operation:input.operation,origin:structural(origin),target:structural(unit),parent:structural(parent),type,
    originPath:pathOf(origin,indexNodes(snapshot[source])),beforePath:unit?pathOf(unit,indexNodes(snapshot[target])):'Unité absente',
    afterPath:input.operation==='rename'?pathOf(unit,indexNodes(snapshot[target])).split(' / ').slice(0,-1).concat(origin.name).join(' / '):pathOf(parent,indexNodes(snapshot[target]))+' / '+(unit?.name||origin.name),
    impactCount:move?.impactCount||1,levels};
}
function canonical(value){if(Array.isArray(value))return value.map(canonical);if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])]));return value;}
export function assertSamePlan(expected,actual){if(JSON.stringify(canonical(expected))!==JSON.stringify(canonical(actual)))throw Error('Les relevés ou correspondances ont changé. Recréer l’action après actualisation.');}
