'use client';
import {useState} from 'react';
import {OPERATIONS,mappedId,targetType,parentCandidates,planSync} from '../lib/sync-plan.mjs';
import {relevantDhis,siteStatus} from '../lib/scope.mjs';
import {pathOf,indexNodes} from '../lib/reconcile.mjs';
import {can} from '../lib/permissions.mjs';
export default function SyncAction({state,user,row,onState}:any){
  const [source,setSource]=useState(state.truthSource||'dhis'),[originId,setOrigin]=useState(row?.[state.truthSource||'dhis']?.id||''),[operation,setOperation]=useState(row?.disc&&row?.dhis?(row.status==='parent'?'move':'rename'):'create');
  const [parentId,setParent]=useState(''),[search,setSearch]=useState(''),[parentSearch,setParentSearch]=useState(''),[full,setFull]=useState(false),[reason,setReason]=useState(''),[confirmed,setConfirmed]=useState(false),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
  if(!can(user.role,'edit'))return null;
  const target=source==='dhis'?'disc':'dhis',nodes=state.snapshot?.[source]||[],origin=nodes.find((n:any)=>n.id===originId),targetId=mappedId(state.mappings,source,originId);
  const type=origin?targetType(origin,source,state.levels):'';
  const candidates=origin?parentCandidates(state.snapshot,state.mappings,source,origin,type,state.levels):[];
  const effectiveParent=parentId||(candidates.length===1?candidates[0].id:'');
  const input={originSource:source,originId,operation,parentId:effectiveParent};
  let plan:any=null,error='';try{plan=planSync(state.snapshot,state.mappings,state.levels,input);}catch(e){error=e instanceof Error?e.message:'Sélection incomplète.';}
  const options=nodes.filter((n:any)=>full||source==='disc'||relevantDhis(n)).filter((n:any)=>(n.name+' '+n.id).toLowerCase().includes(search.toLowerCase()));
  const selectedOutside=origin&&!options.slice(0,150).some((n:any)=>n.id===origin.id);
  async function send(action:string){setBusy(true);setNotice('');try{
    const r=await fetch('/api/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...input,action,reason,reviewPlan:plan,confirmed,backupConfirmed:confirmed,maintenanceConfirmed:confirmed})}),s=await r.json();
    if(!r.ok)throw Error(s.error);onState(s);setConfirmed(false);setNotice(action==='add'?'Action ajoutée à la liste de synchronisation.':'Action confirmée : exécution en arrière-plan.');
  }catch(e){setNotice(e instanceof Error?e.message:'Opération impossible.');}finally{setBusy(false);}}
  return <section className="sync-action"><h3>Synchroniser une structure</h3><p>La référence fournit le nom et la branche. La modification s’applique à la plateforme cible.</p>
    <label className="field">Référence pour cette action<select value={source} onChange={e=>{const s=e.target.value;setSource(s);setOrigin(row?.[s]?.id||'');setParent('');setConfirmed(false);}}><option value="dhis">DHIS2 → DISC-Mali</option><option value="disc">DISC-Mali → DHIS2</option></select></label>
    <label className="field">Rechercher l’unité de référence<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Nom ou identifiant"/></label>
    <label className="check-label"><input type="checkbox" checked={full} onChange={e=>setFull(e.target.checked)}/>Explorer toute l’arborescence</label>
    <label className="field">Unité de référence<select value={originId} onChange={e=>{const id=e.target.value;setOrigin(id);setParent('');setConfirmed(false);setOperation(mappedId(state.mappings,source,id)?'rename':'create');}}><option value="">Choisir (150 premiers résultats)</option>{selectedOutside&&<option value={origin.id}>{origin.name} · {origin.id}</option>}{options.slice(0,150).map((n:any)=><option key={n.id} value={n.id}>{n.name} · {n.id}</option>)}</select></label>
    {origin&&source==='dhis'&&origin.level===6&&<p>{siteStatus(origin)}</p>}
    <label className="field">Opération<select value={operation} onChange={e=>{setOperation(e.target.value);setConfirmed(false);}}>{Object.entries(OPERATIONS).map(([id,label])=><option key={id} value={id} disabled={id==='create'?!!targetId:!targetId}>{label}</option>)}</select></label>
    {operation!=='rename'&&<><label className="field">Rechercher le parent cible<input value={parentSearch} onChange={e=>setParentSearch(e.target.value)}/></label><label className="field">Parent sur {target==='disc'?'DISC-Mali':'DHIS2'}<select value={effectiveParent} onChange={e=>{setParent(e.target.value);setConfirmed(false);}}><option value="">Choisir un parent compatible</option>{candidates.filter((n:any)=>n.id===effectiveParent||(n.name+' '+n.id).toLowerCase().includes(parentSearch.toLowerCase())).slice(0,150).map((n:any)=><option key={n.id} value={n.id}>{pathOf(n,indexNodes(state.snapshot[target]))} · {n.id}</option>)}</select></label><p>Les parents proposés appartiennent à la branche d’un ancêtre rapproché. Un site ASC DISC se rattache à une zone de supervision.</p></>}
    {plan?<div className="plan-summary"><p><b>{OPERATIONS[operation as keyof typeof OPERATIONS]} sur {target==='disc'?'DISC-Mali':'DHIS2'}</b></p><p>Référence : {plan.originPath}</p><p>Avant : {plan.beforePath}</p><p>Après : {plan.afterPath}</p><p>{plan.impactCount} structures dans la branche{operation==='move'&&target==='disc'?' ; les contacts et rapports seront préparés par CHT':''}.</p></div>:origin&&<p className="notice">{error}</p>}
    <label className="field">Justification<textarea minLength={10} maxLength={2000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
    <button className="button" disabled={busy||!plan||reason.trim().length<10} onClick={()=>send('add')}>Ajouter à la liste</button>
    {can(user.role,'execute')&&<><label className="check-label"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Je confirme cette opération sur {target==='disc'?'DISC-Mali':'DHIS2'}, la sauvegarde vérifiée et la disponibilité de la plateforme pour l’appliquer.</label><button className="button primary" disabled={busy||!plan||!confirmed||!state.writesEnabled||reason.trim().length<10} onClick={()=>send('execute-now')}>Appliquer maintenant en arrière-plan</button></>}
    {!state.writesEnabled&&<p>Les écritures distantes sont désactivées sur le serveur. L’ajout à la liste reste disponible.</p>}
    {notice&&<p role="status" className="notice">{notice}</p>}
  </section>;
}
