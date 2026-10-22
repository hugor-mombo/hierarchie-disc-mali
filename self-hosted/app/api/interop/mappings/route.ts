import {transaction,audit} from '../../../../lib/database.mjs';
import {authorizeInterop,mappingManifest} from '../../../../lib/interop.mjs';
import {apiError} from '../../../../lib/auth.mjs';
export async function GET(request:Request){try{
 authorizeInterop(request,'read');
 const result=await transaction(async(c:any)=>{
  await c.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');
  const snapshot=(await c.query("SELECT value FROM app_records WHERE key='snapshot'")).rows[0]?.value;
  const maps=(await c.query('SELECT disc_id AS "discId",dhis_id AS "dhisId" FROM unit_mappings ORDER BY disc_id')).rows;
  const document=mappingManifest(snapshot,maps);
  const created=await c.query('INSERT INTO interop_manifests(version,document) VALUES($1,$2) ON CONFLICT DO NOTHING RETURNING version',[document.version,JSON.stringify(document)]);
  if(created.rowCount)await audit(c,'openfn','interop-manifest',{version:document.version,sites:document.mappings.length});
  return document;
 });
 return Response.json(result,{headers:{'Cache-Control':'no-store'}});
}catch(e){return apiError(e);}}
