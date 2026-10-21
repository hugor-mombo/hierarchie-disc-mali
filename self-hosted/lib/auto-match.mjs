import {DEFAULT_LEVELS,indexNodes,ancestors,matchingName} from './reconcile.mjs';
import {relevantDhis} from './scope.mjs';

// Only reciprocal, unique matches are accepted. Parents are established first;
// disabled intermediate levels (supervision, DHIS level 4) are traversed.
export function automaticMappings(snapshot,mappings=[],levels=DEFAULT_LEVELS,excluded=[]){
  if(!snapshot)return [];
  const disc=snapshot.disc||[],dhis=snapshot.dhis||[],di=indexNodes(disc),hi=indexNodes(dhis);
  const confirmed=new Map(mappings.map(m=>[m.discId,m.dhisId])),used=new Set(mappings.map(m=>m.dhisId)),blocked=new Set(excluded);
  const da=new Map(disc.map(n=>[n.id,ancestors(n,di)])),ha=new Map(dhis.map(n=>[n.id,ancestors(n,hi)]));
  const validPath=(node,index)=>{const seen=new Set();let n=node;while(n){if(seen.has(n.id))return false;seen.add(n.id);if(!n.parent)return true;n=index.get(n.parent);if(!n)return false;}return false;};
  const validDisc=new Set(disc.filter(n=>validPath(n,di)).map(n=>n.id)),validDhis=new Set(dhis.filter(n=>validPath(n,hi)).map(n=>n.id));
  const byName=new Map();
  for(const h of dhis){if(!relevantDhis(h)||!validDhis.has(h.id))continue;const key=h.level+'|'+matchingName(h.name);if(!byName.has(key))byName.set(key,[]);byName.get(key).push(h);}
  function sameBranch(d,h){
    const parent=da.get(d.id).find(n=>levels[n.type]!=null);
    if(!d.parent)return !h.parent&&levels[d.type]===1;
    if(!parent||!confirmed.has(parent.id))return false;
    const counterpart=ha.get(h.id).find(n=>n.level===Number(levels[parent.type]));
    return counterpart?.id===confirmed.get(parent.id);
  }
  const additions=[];
  // At most one pass per hierarchy level, plus a pass for the root.
  for(let pass=0;pass<=TIER_LIMIT;pass++){
    const options=[],claims=new Map();
    for(const d of disc){
      const level=levels[d.type];
      if(confirmed.has(d.id)||level==null||!validDisc.has(d.id))continue;
      let candidates,basis;
      if(d.dhisId){const h=hi.get(d.dhisId);candidates=h&&relevantDhis(h)&&validDhis.has(h.id)&&h.level===Number(level)?[h]:[];basis='embedded-id';}
      else{const name=matchingName(d.name);if(!name)continue;candidates=byName.get(Number(level)+'|'+name)||[];basis='name-level-parent';}
      candidates=candidates.filter(h=>!used.has(h.id)&&sameBranch(d,h));
      for(const h of candidates)claims.set(h.id,(claims.get(h.id)||0)+1);
      options.push({d,candidates,basis});
    }
    const batch=options.filter(o=>!blocked.has(o.d.id)&&o.candidates.length===1&&claims.get(o.candidates[0].id)===1);
    if(!batch.length)break;
    for(const {d,candidates,basis} of batch){const h=candidates[0];confirmed.set(d.id,h.id);used.add(h.id);additions.push({discId:d.id,dhisId:h.id,method:'automatic',matchBasis:basis});}
  }
  return additions;
}
const TIER_LIMIT=12;
