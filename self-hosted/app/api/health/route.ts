import {query} from '../../../lib/database.mjs';export const dynamic='force-dynamic';
export async function GET(){try{await query('SELECT 1 FROM schema_migrations LIMIT 1');return Response.json({status:'ok'});}catch{return Response.json({status:'unavailable'},{status:503});}}
