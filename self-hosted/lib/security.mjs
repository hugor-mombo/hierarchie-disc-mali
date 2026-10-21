import {randomBytes,scrypt as scryptCallback,timingSafeEqual,createHash} from 'node:crypto';import {promisify} from 'node:util';
const scrypt=promisify(scryptCallback);
export {ROLES,can} from './permissions.mjs';
export function validatePassword(password){if(typeof password!=='string'||password.length<12||Buffer.byteLength(password)>256)throw Error('Le mot de passe doit contenir 12 à 256 caractères maximum.');}
export async function hashPassword(password){validatePassword(password);const salt=randomBytes(16).toString('hex');const hash=await scrypt(password,salt,64,{N:32768,r:8,p:1,maxmem:64*1024*1024});return ['scrypt',salt,hash.toString('hex')].join('$');}
export async function verifyPassword(password,stored){if(typeof password!=='string'||Buffer.byteLength(password)>256)return false;const [scheme,salt,hex]=stored.split('$');if(scheme!=='scrypt'||!salt||!hex)return false;const expected=Buffer.from(hex,'hex');const actual=await scrypt(password,salt,64,{N:32768,r:8,p:1,maxmem:64*1024*1024});return expected.length===actual.length&&timingSafeEqual(expected,actual);}
export const digest=value=>createHash('sha256').update(value).digest('hex');
export function sessionToken(){const token=randomBytes(32).toString('base64url');return {token,hash:digest(token)};}
export function assertOrigin(request){const origin=request.headers.get('origin');const expected=process.env.APP_URL;if(!expected||!origin||origin!==new URL(expected).origin||request.headers.get('sec-fetch-site')==='cross-site')throw Object.assign(Error('Origine refusée.'),{status:403});}
export function assertIndependent(requester,reviewer){if(requester===reviewer)throw Error('Une autre personne doit approuver cette demande.');}
