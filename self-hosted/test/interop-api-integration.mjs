import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
if(!process.env.DATABASE_URL||!new URL(process.env.DATABASE_URL).pathname.endsWith('_qa')||process.env.DISC_URL!=='https://disc.example')throw Error('Base QA requise.');
const {query,pool}=await import('../lib/database.mjs'),{hashPassword}=await import('../lib/security.mjs'),{demoState}=await import('../lib/demo.mjs');
const base='http://web:3000',id=randomUUID(),password='QA-'+randomUUID(),username='interop-qa';
try{
 const s=demoState();s.snapshot.updatedAt=new Date().toISOString();
 await query("INSERT INTO app_records(key,value) VALUES('snapshot',$1)",[JSON.stringify(s.snapshot)]);
 for(const m of s.mappings)await query('INSERT INTO unit_mappings(disc_id,dhis_id,actor) VALUES($1,$2,$3)',[m.discId,m.dhisId,'qa']);
 await query('INSERT INTO app_users(id,username,display_name,password_hash,role,must_change_password) VALUES($1,$2,$3,$4,$5,false)',[id,username,'Recette OpenFn',await hashPassword(password),'viewer']);
 const headers={authorization:'Bearer '+process.env.OPENFN_MAPPING_TOKEN};
 assert.equal((await fetch(base+'/api/interop/mappings')).status,401);
 let r=await fetch(base+'/api/interop/mappings',{headers});assert.equal(r.status,200);const manifest=await r.json();assert.equal(manifest.mappings.length,3);assert.equal(r.headers.get('cache-control'),'no-store');
 const mapping=manifest.mappings[0],event={eventId:randomUUID(),runId:'qa-run',workflow:'qa-only',mappingVersion:manifest.version,period:'202609',dataset:'qa-dataset',...mapping,mode:'test',status:'dry_run',counts:{prepared:1,accepted:0,rejected:0}};
 const post=(e=event,token=process.env.OPENFN_AUDIT_TOKEN)=>fetch(base+'/api/interop/events',{method:'POST',headers:{authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(e)});
 assert.equal((await post(event,process.env.OPENFN_MAPPING_TOKEN)).status,401);
 assert.equal((await post()).status,200);assert.equal((await (await post()).json()).duplicate,true);
 assert.equal((await post({...event,status:'failed'})).status,409);
 assert.equal((await post({...event,eventId:randomUUID(),dhis2_org_unit:'wrong'})).status,409);
 assert.equal((await post({...event,eventId:randomUUID(),status:'reported_success'})).status,400);
 assert.equal((await query('SELECT count(*)::int AS count FROM interop_events')).rows[0].count,1);
 assert.equal((await fetch(base+'/api/interop')).status,401);
 r=await fetch(base+'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json',Origin:process.env.APP_URL},body:JSON.stringify({username,password})});assert.equal(r.status,200);const cookie=r.headers.get('set-cookie').split(';')[0];
 r=await fetch(base+'/api/interop?period=202609',{headers:{cookie}});assert.equal(r.status,200);assert.equal((await r.json()).events.length,1);
 r=await fetch(base+'/api/interop?period=202608',{headers:{cookie}});assert.equal((await r.json()).events.length,0);
 s.snapshot.dhis.find(n=>n.id===mapping.dhis2_org_unit).closedDate='2020-01-01';await query("UPDATE app_records SET value=$1 WHERE key='snapshot'",[JSON.stringify(s.snapshot)]);
 const next=await (await fetch(base+'/api/interop/mappings',{headers})).json();assert.notEqual(next.version,manifest.version);assert.equal(next.mappings.length,2);
 assert.equal((await query('SELECT document FROM interop_manifests WHERE version=$1',[manifest.version])).rows[0].document.mappings.length,3);
 s.snapshot.updatedAt='2020-01-01T00:00:00Z';await query("UPDATE app_records SET value=$1 WHERE key='snapshot'",[JSON.stringify(s.snapshot)]);assert.equal((await fetch(base+'/api/interop/mappings',{headers})).status,409);
 console.log('OK : authentification machine distincte, manifeste figé et versionné, refus des relevés périmés, audit idempotent, filtres protégés et simulations séparées.');
}finally{
 await query('DELETE FROM interop_events');await query('DELETE FROM interop_manifests');await query('DELETE FROM unit_mappings');await query('DELETE FROM app_records');await query('DELETE FROM app_users WHERE id=$1',[id]);await pool().end();
}
