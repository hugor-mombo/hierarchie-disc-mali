import {readdir,readFile} from 'node:fs/promises';import {query,transaction,pool} from '../lib/database.mjs';
await query('CREATE TABLE IF NOT EXISTS schema_migrations(name text PRIMARY KEY,applied_at timestamptz NOT NULL DEFAULT now())');
for(const file of (await readdir(new URL('../migrations/',import.meta.url))).filter(n=>n.endsWith('.sql')).sort()){
 await transaction(async c=>{await c.query("SELECT pg_advisory_xact_lock(hashtext('hierarchie:migrate'))");if((await c.query('SELECT 1 FROM schema_migrations WHERE name=$1',[file])).rowCount)return;await c.query(await readFile(new URL('../migrations/'+file,import.meta.url),'utf8'));await c.query('INSERT INTO schema_migrations(name) VALUES($1)',[file]);console.log('Migration : '+file);});
}await pool().end();
