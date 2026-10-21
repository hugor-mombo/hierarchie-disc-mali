// Official CHT recursive deletion preparation. No remote write is permitted here.
const environment=require('cht-conf/src/lib/environment'),log=require('cht-conf/src/lib/log');
process.umask(0o077);log.level=log.LEVEL_ERROR;
const url=new URL(process.env.DISC_URL||'https://disc-mali.ml');url.username=process.env.DISC_WRITE_USER||process.env.DISC_USER;url.password=process.env.DISC_WRITE_PASSWORD||process.env.DISC_PASSWORD;url.pathname=url.pathname.replace(/\/$/,'')+'/medic';
environment.initialize(process.cwd(),false,null,[`--contacts=${process.env.DELETE_UNIT}`,`--docDirectoryPath=${process.env.DELETE_DIRECTORY}`,'--force'],url,true,false,false);
const dbPath=require.resolve('cht-conf/src/lib/db');require(dbPath);const PouchDB=require('pouchdb-core');
const db=new PouchDB(environment.apiUrl,{skip_setup:true});for(const method of ['put','post','bulkDocs','remove','destroy'])db[method]=()=>Promise.reject(Error('Écriture interdite pendant la préparation'));
require.cache[dbPath].exports=()=>db;
// Contact IDs may contain slashes; never use them as local paths.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
require('cht-conf/src/lib/hierarchy-operations/jsdocFolder').deleteDoc=(options,doc,disableUsers)=>{
 if(disableUsers)throw Error('Modification des comptes interdite');
 const name=crypto.createHash('sha256').update(doc._id).digest('hex')+'.doc.json';
 fs.writeFileSync(path.join(options.docDirectoryPath,name),JSON.stringify({_id:doc._id,_rev:doc._rev,_deleted:true,cht_disable_linked_users:false}),{mode:0o600});
};
(async()=>{
 if(process.env.DELETE_VERIFY_FILE){
  const data=require('cht-conf/src/lib/hierarchy-operations/hierarchy-data-source'),ids=JSON.parse(fs.readFileSync(process.env.DELETE_VERIFY_FILE,'utf8'));
  if((await data.getContactWithDescendants(db,process.env.DELETE_UNIT)).length)throw Error('Contacts encore présents');
  if((await data.fetchReportsBySubject(db,ids,0)).length)throw Error('Rapports sujets encore présents');
  if((await data.fetchReportsByCreator(db,ids,null,await data.useNouveauSearch())).docs.length)throw Error('Rapports émetteurs encore présents');
  return;
 }
 await require('cht-conf/src/fn/delete-contacts').execute();
 // Also include reports submitted by these contacts, in addition to subject reports
 // collected by the official deletion action. Never disable or delete user accounts.
 const data=require('cht-conf/src/lib/hierarchy-operations/hierarchy-data-source');
 const files=require('cht-conf/src/lib/hierarchy-operations/jsdocFolder');
 const contacts=await data.getContactWithDescendants(db,process.env.DELETE_UNIT);
 const nouveau=await data.useNouveauSearch();let cursor=null;
 do{const batch=await data.fetchReportsByCreator(db,contacts.map(d=>d._id),cursor,nouveau);for(const d of batch.docs)files.deleteDoc({docDirectoryPath:process.env.DELETE_DIRECTORY},d,false);cursor=batch.cursor;if(batch.docs.length<data.BATCH_SIZE)break;}while(cursor);
})().then(()=>process.exit(0)).catch(()=>{process.stderr.write('Préparation de suppression CHT refusée : vérifier les accès et le périmètre.\n');process.exit(1);});
