// Isolated official cht-conf preparation: credentials stay in process environment.
// This action only writes staged files. Remote upload is performed separately.
const path=require('node:path');const environment=require('cht-conf/src/lib/environment');const log=require('cht-conf/src/lib/log');
process.umask(0o077);log.level=log.LEVEL_ERROR;
const url=new URL(process.env.DISC_URL||'https://disc-mali.ml');url.username=process.env.DISC_WRITE_USER||process.env.DISC_USER;url.password=process.env.DISC_WRITE_PASSWORD||process.env.DISC_PASSWORD;url.pathname=url.pathname.replace(/\/$/,'')+'/medic';
environment.initialize(process.cwd(),false,null,[`--contacts=${process.env.MOVE_UNIT}`,`--parent=${process.env.MOVE_PARENT}`,`--docDirectoryPath=${process.env.MOVE_DIRECTORY}`,'--force'],url,true,false,false);
// Disable database creation and document writes during preparation. The official
// hierarchy algorithm still performs the lineage transformation and constraints.
const dbPath=require.resolve('cht-conf/src/lib/db');require(dbPath);const PouchDB=require('pouchdb-core');
require.cache[dbPath].exports=()=>{const db=new PouchDB(environment.apiUrl,{skip_setup:true});for(const method of ['put','post','bulkDocs','remove','destroy'])db[method]=()=>Promise.reject(new Error('Remote writes are disabled during preparation'));return db;};
require('cht-conf/src/fn/move-contacts').execute().then(()=>process.exit(0)).catch(()=>{process.stderr.write('La préparation officielle CHT a échoué (vérifier droits, configuration et hiérarchie).\n');process.exit(1);});
