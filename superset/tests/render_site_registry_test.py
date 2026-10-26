"""Assembler la fixture psql avec les vraies sources SQL, sans accès réseau."""
from pathlib import Path
root=Path(__file__).resolve().parent
lines=(root/'site_registry.sql').read_text().splitlines()
for line in lines:
 if line.startswith('\\ir '):print((root/line[4:]).resolve().read_text())
 else:print(line)
