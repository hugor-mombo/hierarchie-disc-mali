import {readState} from '../../../lib/state.mjs';import {requireUser,apiError} from '../../../lib/auth.mjs';
export const dynamic='force-dynamic';export const runtime='nodejs';
export async function GET(r:Request){try{const user=await requireUser(r);return Response.json({...await readState(),user},{headers:{'Cache-Control':'no-store'}});}catch(e){return apiError(e);}}
