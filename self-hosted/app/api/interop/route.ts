import {requireUser,apiError} from '../../../lib/auth.mjs';
import {query} from '../../../lib/database.mjs';
export async function GET(request:Request){try{
 await requireUser(request);
 const params=new URL(request.url).searchParams,site=(params.get('site')||'').slice(0,160),period=(params.get('period')||'').slice(0,8);
 const events=(await query('SELECT id,received_at,payload FROM interop_events WHERE ($1=\'\' OR payload->>\'chw_site_id\'=$1 OR payload->>\'dhis2_org_unit\'=$1) AND ($2=\'\' OR payload->>\'period\'=$2) ORDER BY id DESC LIMIT 200',[site,period])).rows;
 return Response.json({events,configured:!!((process.env.OPENFN_MAPPING_TOKEN||'').length>=32&&(process.env.OPENFN_AUDIT_TOKEN||'').length>=32)},{headers:{'Cache-Control':'no-store'}});
}catch(e){return apiError(e);}}
