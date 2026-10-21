import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {demoState} from '../lib/demo.mjs';
import {planSync} from '../lib/sync-plan.mjs';
import {executeSync} from '../lib/sync-executor.mjs';
import {CSCOM_GROUP,ASC_GROUP} from '../lib/scope.mjs';

import {fixture} from './fixtures/sync-platforms.mjs';

test('connecteurs : création et renommage dans les deux sens, préconditions et erreurs partielles',async()=>{
  const dir=await mkdtemp(path.join(tmpdir(),'hierarchie-sync-')),original=globalThis.fetch;
  try{
    let f=await fixture(dir);globalThis.fetch=f.fetcher;let wrote=false;
    let r=await executeSync(f.row({originId:'h11',operation:'create',parentId:'d4'}),f.env,f.s.mappings,f.s.levels,()=>{wrote=true;});
    assert.equal(wrote,true);assert.equal(r.targetId,'created-qa');assert.deepEqual(f.writes,['disc-create']);assert.equal(f.docs.get(r.targetId).dhis2_org_unit,'h11');
    f=await fixture(dir);globalThis.fetch=f.fetcher;
    r=await executeSync(f.row({originSource:'disc',originId:'d10',operation:'create',parentId:'h4'}),f.env,f.s.mappings,f.s.levels);
    assert.deepEqual(f.writes,['dhis-create','dhis-group']);assert.ok(f.s.snapshot.dhis.find(n=>n.id===r.targetId).groups.includes(ASC_GROUP));
    f=await fixture(dir);globalThis.fetch=f.fetcher;
    await executeSync(f.row({originId:'h5',operation:'rename'}),f.env,f.s.mappings,f.s.levels);assert.equal(f.docs.get('d5').name,'NGOLOBOUGOU');
    f=await fixture(dir);globalThis.fetch=f.fetcher;
    await executeSync(f.row({originSource:'disc',originId:'d5',operation:'rename'}),f.env,f.s.mappings,f.s.levels);assert.equal(f.s.snapshot.dhis.find(n=>n.id==='h5').name,'Site ASC de N’Golobougou');
    f=await fixture(dir);globalThis.fetch=f.fetcher;let row=f.row({originId:'h11',operation:'create',parentId:'d4'});
    f.s.snapshot.dhis.find(n=>n.id==='h11').name='Nom changé';await assert.rejects(executeSync(row,f.env,f.s.mappings,f.s.levels),/changé/);assert.equal(f.writes.length,0);
    f=await fixture(dir);globalThis.fetch=f.fetcher;row=f.row({originId:'h11',operation:'create',parentId:'d4'});
    await assert.rejects(executeSync(row,{...f.env,ENABLE_REMOTE_WRITES:'false'},f.s.mappings,f.s.levels),/désactivées/);assert.equal(f.calls.length,0);
    await assert.rejects(executeSync(row,{...f.env,DISC_URL:'https://other.example'},f.s.mappings,f.s.levels),/URL/);assert.equal(f.calls.length,0);
    f=await fixture(dir);globalThis.fetch=f.fetcher;f.fail();wrote=false;
    await assert.rejects(executeSync(f.row({originSource:'disc',originId:'d10',operation:'create',parentId:'h4'}),f.env,f.s.mappings,f.s.levels,()=>{wrote=true;}),/HTTP 503/);
    assert.equal(wrote,true);assert.deepEqual(f.writes,['dhis-create']);
  }finally{globalThis.fetch=original;await rm(dir,{recursive:true,force:true});}
});
