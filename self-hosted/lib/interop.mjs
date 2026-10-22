import {createHash,timingSafeEqual} from 'node:crypto';
import {siteMappingReport} from './site-mappings.mjs';
export const INTEROP_STATUSES=['running','dry_run','reported_success','partial','failed','no_data','blocked'];
export function interopError(message,status=400){return Object.assign(Error(message),{status});}
export function authorizeInterop(request,scope,env=process.env){
 const expected=env[scope==='read'?'OPENFN_MAPPING_TOKEN':'OPENFN_AUDIT_TOKEN'];
 if(!expected||expected.length<32)throw interopError('Connexion OpenFn non configurée.',503);
 const actual=request.headers.get('authorization')?.replace(/^Bearer /,'')||'';
 const hash=value=>createHash('sha256').update(value).digest();
 if(!timingSafeEqual(hash(actual),hash(expected)))throw interopError('Accès technique refusé.',401);
}
export function mappingManifest(snapshot,mappings,now=new Date(),maxAgeHours=48){
 const age=now.getTime()-Date.parse(snapshot?.updatedAt);
 if(!Number.isFinite(age)||age< -300000||age>maxAgeHours*3600000)throw interopError('Relevés trop anciens : actualiser DISC et DHIS2 avant un traitement OpenFn.',409);
 const date=now.toISOString().slice(0,10),report=siteMappingReport(snapshot,mappings,date);
 if(!report.rows.length)throw interopError('Aucune correspondance de site ASC ouvert disponible.',409);
 const body={schemaVersion:1,kind:'asc-sites',effectiveDate:date,snapshotAt:snapshot.updatedAt,
  mappings:report.rows.map(r=>({chw_site_id:r.discId,dhis2_org_unit:r.dhisId,active:true,site_disc:r.discName,site_dhis2:r.dhisName,chemin_disc:r.discPath,chemin_dhis2:r.dhisPath})),dhisSites:report.dhisSites,excluded:report.excluded.length};
 return {version:createHash('sha256').update(JSON.stringify(body)).digest('hex'),...body};
}
function text(value,label,max=160){if(typeof value!=='string'||!value.trim()||value.length>max||/[\x00-\x1f]/.test(value))throw interopError(label+' invalide.');return value;}
export function validateInteropEvent(input,manifest){
 if(!input||typeof input!=='object'||Array.isArray(input))throw interopError('Événement invalide.');
 const event={eventId:text(input.eventId,'Identifiant événement'),runId:text(input.runId,'Identifiant exécution'),mappingVersion:text(input.mappingVersion,'Version mapping',64),
  workflow:text(input.workflow,'Workflow'),period:text(input.period,'Période',8),dataset:text(input.dataset,'Dataset',64),
  chw_site_id:text(input.chw_site_id,'Site DISC'),dhis2_org_unit:text(input.dhis2_org_unit,'UO DHIS2'),status:input.status,mode:input.mode};
 if(!/^\d{4}(0[1-9]|1[0-2])$/.test(event.period)&&!/^\d{4}W(0[1-9]|[1-4]\d|5[0-3])$/.test(event.period))throw interopError('Période mensuelle ou hebdomadaire attendue.');
 if(!INTEROP_STATUSES.includes(event.status)||!['test','live'].includes(event.mode))throw interopError('Statut ou mode inconnu.');
 if(event.mode==='test'&&event.status==='reported_success')throw interopError('Un test ne peut pas déclarer un envoi réel réussi.');
 if(!manifest||manifest.version!==event.mappingVersion||!manifest.mappings.some(m=>m.chw_site_id===event.chw_site_id&&m.dhis2_org_unit===event.dhis2_org_unit))throw interopError('Correspondance absente de la version fournie.',409);
 event.counts={};
 for(const key of ['prepared','accepted','rejected']){const n=input.counts?.[key];if(!Number.isSafeInteger(n)||n<0)throw interopError('Compteurs invalides.');event.counts[key]=n;}
 if(event.counts.accepted+event.counts.rejected>event.counts.prepared)throw interopError('Compteurs incohérents.');
 if(event.status==='reported_success'&&(!event.counts.prepared||event.counts.accepted!==event.counts.prepared||event.counts.rejected))throw interopError('Succès incompatible avec les compteurs.');
 // No health payloads, free-form errors, credentials or arbitrary callback URLs.
 event.errorCode=input.errorCode?text(input.errorCode,'Code erreur',80):null;
 if(event.errorCode&&!/^[A-Z0-9_.:-]+$/.test(event.errorCode))throw interopError('Code erreur non admissible.');
 return event;
}
