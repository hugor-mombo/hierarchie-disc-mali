// Run only in the disposable QA stack; no live platform call is made.
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
if(!process.env.DATABASE_URL||!new URL(process.env.DATABASE_URL).pathname.endsWith('_qa')||process.env.DISC_URL!=='https://disc.example')throw Error('Base QA requise.');
const {query,pool}=await import('../lib/database.mjs'),{hashPassword}=await import('../lib/security.mjs'),{demoState}=await import('../lib/demo.mjs'),{parseMappings}=await import('../lib/reconcile.mjs'),{siteMappingReport}=await import('../lib/site-mappings.mjs');
const base='http://web:3000',origin=process.env.APP_URL,id=randomUUID(),username='site-mapping-qa',password='QA-'+randomUUID();
try{
 await query('INSERT INTO app_users(id,username,display_name,password_hash,role,must_change_password) VALUES($1,$2,$3,$4,$5,false)',[id,username,'Recette mappage',await hashPassword(password),'editor']);
 const s=demoState();await query("INSERT INTO app_records(key,value) VALUES('snapshot',$1)",[JSON.stringify(s.snapshot)]);for(const m of s.mappings)await query('INSERT INTO unit_mappings(disc_id,dhis_id,actor) VALUES($1,$2,$3)',[m.discId,m.dhisId,'qa']);
 const url=base+'/api/export?type=asc-mappings';assert.equal((await fetch(url)).status,401);
 let r=await fetch(base+'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json',Origin:origin},body:JSON.stringify({username,password})});assert.equal(r.status,200);const cookie=r.headers.get('set-cookie').split(';')[0],headers={cookie};
 r=await fetch(url,{headers});assert.equal(r.status,200);assert.equal(r.headers.get('cache-control'),'no-store');assert.match(r.headers.get('content-disposition'),/OrgUnits Mapping - Sites ASC.csv/);let text=await r.text();assert.equal(text.replace(/^\ufeff/,'').split('\r\n')[0],'"chw_site_id","dhis2_org_unit","active"');let pairs=parseMappings(text);
 let maps=(await query('SELECT disc_id AS "discId",dhis_id AS "dhisId" FROM unit_mappings')).rows;assert.equal(pairs.length,siteMappingReport(s.snapshot,maps).rows.length);assert.ok(!pairs.some(p=>p.discId==='d9'));
 r=await fetch(base+'/api/actions',{method:'POST',headers:{cookie,Origin:origin,'Content-Type':'application/json'},body:JSON.stringify({action:'approve',discId:'d9',dhisId:'h9'})});assert.equal(r.status,200);
 pairs=parseMappings(await (await fetch(url,{headers})).text());assert.ok(pairs.some(p=>p.discId==='d9'&&p.dhisId==='h9'));
 await query("INSERT INTO unit_mappings(disc_id,dhis_id,actor) VALUES('d10','absent','qa')");pairs=parseMappings(await (await fetch(url,{headers})).text());assert.ok(!pairs.some(p=>p.discId==='d10'));
 delete s.snapshot.dhis.find(n=>n.id==='h5').groups;await query("UPDATE app_records SET value=$1 WHERE key='snapshot'",[JSON.stringify(s.snapshot)]);assert.notEqual((await fetch(url,{headers})).status,200);
 console.log('OK : export CSV ASC authentifié, trois colonnes conservées, propositions exclues, fichier actualisé après rapprochement, lien cassé exclu et ancien relevé refusé.');
}finally{await query('DELETE FROM unit_mappings');await query('DELETE FROM app_records');await query('DELETE FROM app_users WHERE id=$1',[id]);await pool().end();}
