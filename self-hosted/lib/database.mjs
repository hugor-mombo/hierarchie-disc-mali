import 'dotenv/config';
import pg from 'pg';
const globalKey=Symbol.for('hierarchie.pg');
export function pool(){if(!globalThis[globalKey]){if(!process.env.DATABASE_URL)throw Error('DATABASE_URL non configurée.');globalThis[globalKey]=new pg.Pool({connectionString:process.env.DATABASE_URL,max:10,connectionTimeoutMillis:10000,ssl:process.env.PGSSL==='true'?{rejectUnauthorized:true}:undefined});}return globalThis[globalKey];}
export async function query(text,values=[]){return pool().query(text,values);}
export async function transaction(work){const c=await pool().connect();try{await c.query('BEGIN');const value=await work(c);await c.query('COMMIT');return value;}catch(e){await c.query('ROLLBACK');throw e;}finally{c.release();}}
export async function audit(c,user,action,detail){await c.query('INSERT INTO audit_events(actor,action,detail) VALUES($1,$2,$3)',[user,action,JSON.stringify(detail)]);}
