import {test} from 'node:test';
import assert from 'node:assert/strict';
import {authorizeInterop,mappingManifest,validateInteropEvent} from '../lib/interop.mjs';
import {demoState} from '../lib/demo.mjs';
const now=new Date('2026-10-22T12:00:00Z');
function fixture(){const s=demoState();s.snapshot.updatedAt=now.toISOString();return s;}
test('API technique désactivée sans secret, jetons distincts et session humaine insuffisante',()=>{
 const req=token=>new Request('https://local/api/interop',{headers:token?{authorization:'Bearer '+token}:{cookie:'hierarchie_session=human'}}),env={OPENFN_MAPPING_TOKEN:'a'.repeat(64),OPENFN_AUDIT_TOKEN:'b'.repeat(64)};
 assert.throws(()=>authorizeInterop(req(),'read',{}),{status:503});assert.throws(()=>authorizeInterop(req(),'read',env),{status:401});
 authorizeInterop(req(env.OPENFN_MAPPING_TOKEN),'read',env);assert.throws(()=>authorizeInterop(req(env.OPENFN_MAPPING_TOKEN),'write',env),{status:401});
});
test('manifestes stables, versionnés, ouverts seulement ; refus des relevés périmés',()=>{
 const s=fixture(),manifest=mappingManifest(s.snapshot,s.mappings,now);
 assert.equal(mappingManifest(s.snapshot,[...s.mappings].reverse(),now).version,manifest.version);
 s.snapshot.dhis.find(n=>n.id==='h5').closedDate='2026-10-22';
 const changed=mappingManifest(s.snapshot,s.mappings,now);assert.notEqual(changed.version,manifest.version);assert.ok(!changed.mappings.some(m=>m.dhis2_org_unit==='h5'));
 s.snapshot.updatedAt='2026-10-19T12:00:00Z';assert.throws(()=>mappingManifest(s.snapshot,s.mappings,now),{status:409});
});
test('audit associé au mapping exact ; simulations et compteurs vérifiés ; données arbitraires écartées',()=>{
 const s=fixture(),manifest=mappingManifest(s.snapshot,s.mappings,now),mapping=manifest.mappings[0];
 const event={eventId:'event-1',runId:'run-1',mappingVersion:manifest.version,workflow:'test-sites',period:'202609',dataset:'dummy-dataset',...mapping,status:'dry_run',mode:'test',counts:{prepared:1,accepted:0,rejected:0},password:'never-store'};
 const result=validateInteropEvent(event,manifest);assert.ok(!Object.hasOwn(result,'password'));assert.ok(!Object.hasOwn(result,'site_disc'));
 assert.throws(()=>validateInteropEvent({...event,dhis2_org_unit:'unknown'},manifest),{status:409});
 assert.throws(()=>validateInteropEvent({...event,status:'reported_success'},manifest));
 assert.throws(()=>validateInteropEvent({...event,mode:'live',status:'reported_success'},manifest));
 assert.throws(()=>validateInteropEvent({...event,counts:{prepared:1,accepted:2,rejected:0}},manifest));
 assert.throws(()=>validateInteropEvent({...event,errorCode:'patient John data'},manifest));
 assert.equal(validateInteropEvent({...event,mode:'live',status:'reported_success',counts:{prepared:1,accepted:1,rejected:0}},manifest).status,'reported_success');
});
