// Refresh snapshots and registry mappings only; never writes to DISC or DHIS2.
import {pool} from '../lib/database.mjs';
import {fetchDISC,fetchDHIS} from '../lib/sources.mjs';
import {saveSnapshot} from '../lib/state.mjs';
import {relevantDhis,DISTRICT_GROUP} from '../lib/scope.mjs';
const lock=await pool().connect();let acquired=false;
try{
 acquired=(await lock.query("SELECT pg_try_advisory_lock(hashtext('hierarchie:remote-operations')) AS ok")).rows[0].ok;
 if(!acquired)throw Error('Une opération distante est en cours. Réessayer après son achèvement.');
 const [disc,dhis]=await Promise.all([fetchDISC(process.env),fetchDHIS(process.env)]);
 await saveSnapshot(disc,dhis.nodes,dhis.levels,'operator-refresh',dhis.groupsRead);
 console.log(JSON.stringify({disc:disc.length,dhis:dhis.nodes.length,districtGroup:DISTRICT_GROUP,districtsVisible:dhis.nodes.filter(n=>n.level===3&&relevantDhis(n)).length,groups:dhis.groupsRead}));
}finally{if(acquired)await lock.query("SELECT pg_advisory_unlock(hashtext('hierarchie:remote-operations'))");lock.release();await pool().end();}
