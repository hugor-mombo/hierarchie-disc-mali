// CHT 4.21: merge only tasks.rules through the official settings API.
// Default: validate a patch. --apply is required to write. Never upload local app_settings wholesale.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { isDeepStrictEqual } from 'node:util';
import vm from 'node:vm';

const args = process.argv.slice(2);
const option = name => { const index = args.indexOf(name); return index >= 0 ? args[index + 1] : undefined; };
const sha = value => createHash('sha256').update(value).digest('hex');
const fail = message => { throw new Error(message); };
const replacementPath = option('--replacement');
const rulesPath = option('--rules'); // Exact backed-up bundle, for rollback only.
const expected = option('--expect-sha256');
if ((!replacementPath === !rulesPath) || !/^[a-f0-9]{64}$/.test(expected || '')) {
  fail('Specify exactly one of --replacement or --rules, and --expect-sha256. Optional: --env, --backup-dir, --apply.');
}
process.loadEnvFile(resolve(option('--env') || 'self-hosted/.env'));
const username = process.env.DISC_WRITE_USER || process.env.DISC_USER;
const password = process.env.DISC_WRITE_PASSWORD || process.env.DISC_PASSWORD;
if (!username || !password) fail('DISC credentials are missing.');
const base = (process.env.DISC_URL || 'https://disc-mali.ml').replace(/\/$/, '');
if (!base.startsWith('https://')) fail('HTTPS is required.');
const headers = { Authorization: 'Basic ' + Buffer.from(username + ':' + password).toString('base64') };
const getSettings = async () => {
  const response = await fetch(base + '/api/v1/settings', { headers });
  if (!response.ok) fail('Read settings: HTTP ' + response.status);
  return response.json();
};
const before = await getSettings();
const original = before.tasks?.rules;
if (typeof original !== 'string' || sha(original) !== expected) fail('Live rules differ from the expected baseline; aborting.');
let candidate;
if (rulesPath) {
  candidate = readFileSync(resolve(rulesPath), 'utf8');
} else {
  const marker = 'const childLongitudinalTemplate =';
  const next = '\nconst supervisorRealizationFollowup =';
  const start = original.indexOf(marker);
  const end = original.indexOf(next, start);
  if (start < 0 || end < 0 || original.indexOf(marker, start + marker.length) !== -1) fail('Factory markers are ambiguous.');
  const replacement = readFileSync(resolve(replacementPath), 'utf8').trim();
  if (!replacement.startsWith(marker) || replacement.includes(next)) fail('Invalid replacement factory.');
  new vm.Script(replacement); // Parse without executing clinical code.
  candidate = original.slice(0, start) + replacement + '\n' + original.slice(end);
}
// The complete bundle contains Nools DSL as well as JavaScript; it is tested in the CHT harness.
if (candidate === original) fail('No change.');
const summary = { before: expected, after: sha(candidate), changed_paths: ['tasks.rules'] };
if (!args.includes('--apply')) {
  console.log(JSON.stringify({ ...summary, applied: false }));
  process.exit(0);
}
const backupDir = option('--backup-dir');
if (!backupDir) fail('--backup-dir is required when applying.');
mkdirSync(backupDir, { mode: 0o700, recursive: false }); // Refuse to overwrite an earlier backup.
writeFileSync(resolve(backupDir, 'settings-before.json'), JSON.stringify(before), { mode: 0o600 });
writeFileSync(resolve(backupDir, 'rules-before.js'), original, { mode: 0o600 });
writeFileSync(resolve(backupDir, 'rules-after.js'), candidate, { mode: 0o600 });
// Recheck immediately before merging; other settings are not included in the PUT.
if ((await getSettings()).tasks.rules !== original) fail('Concurrent rules update; aborting.');
const response = await fetch(base + '/api/v1/settings', {
  method: 'PUT', headers: { ...headers, 'Content-Type': 'application/json' },
  body: JSON.stringify({ tasks: { rules: candidate } })
});
if (!response.ok) fail('Write settings: HTTP ' + response.status + '; backup retained.');
const result = await response.json();
if (!result.success) fail('Settings API did not confirm success; verify live settings.');
const after = await getSettings();
if (after.tasks.rules !== candidate) fail('Post-write rules verification failed; verify live settings.');
const withoutRules = settings => {
  const copy = structuredClone(settings);
  delete copy.tasks.rules;
  return copy;
};
if (!isDeepStrictEqual(withoutRules(before), withoutRules(after))) {
  fail('Other settings changed concurrently or were defaulted by CHT; inspect backups before taking action.');
}
const manifest = { ...summary, applied: true, verified_at: new Date().toISOString(), api_result: result };
writeFileSync(resolve(backupDir, 'manifest.json'), JSON.stringify(manifest, null, 2), { mode: 0o600 });
console.log(JSON.stringify(manifest));
