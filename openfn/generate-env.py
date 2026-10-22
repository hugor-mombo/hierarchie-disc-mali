"""Generate secrets on the target host; never overwrite an existing configuration."""
import base64
import os
import pathlib
import secrets
import subprocess
import tempfile

target = pathlib.Path('.env')
if target.exists():
    raise SystemExit('Configuration existante conservée.')
with tempfile.TemporaryDirectory() as directory:
    private = pathlib.Path(directory) / 'private.pem'
    public = pathlib.Path(directory) / 'public.pem'
    subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', str(private)], check=True, capture_output=True)
    subprocess.run(['openssl', 'rsa', '-in', str(private), '-pubout', '-out', str(public)], check=True, capture_output=True)
    values = {
        'LIGHTNING_IMAGE': 'openfn/lightning:v2.18.0',
        'WORKER_IMAGE': 'openfn/ws-worker:latest',
        'POSTGRES_PASSWORD': secrets.token_hex(32),
        'SECRET_KEY_BASE': secrets.token_urlsafe(64),
        'PRIMARY_ENCRYPTION_KEY': base64.b64encode(secrets.token_bytes(32)).decode(),
        'WORKER_SECRET': secrets.token_hex(32),
        'WORKER_RUNS_PRIVATE_KEY': base64.b64encode(private.read_bytes()).decode(),
        'WORKER_LIGHTNING_PUBLIC_KEY': base64.b64encode(public.read_bytes()).decode(),
        'MAX_DATACLIP_SIZE_MB': '10',
        'WORKER_MAX_RUN_DURATION_SECONDS': '300',
        'WORKER_MAX_RUN_MEMORY_MB': '512',
        'RUN_GRACE_PERIOD_SECONDS': '30',
    }
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
        output.write(''.join(f'{key}={value}\n' for key, value in values.items()))
print('Configuration privée générée ; aucun secret affiché.')
