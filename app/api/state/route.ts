import {readState} from '../../../lib/state';
export const dynamic='force-dynamic';
export async function GET(){try{return Response.json(await readState(),{headers:{'Cache-Control':'no-store'}});}catch{return Response.json({error:'Impossible de lire les données enregistrées.'},{status:503});}}
