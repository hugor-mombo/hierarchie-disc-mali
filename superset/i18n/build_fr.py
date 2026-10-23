"""Compile the official Superset 5 French catalog and reviewed local UI overrides.

Output matches po2json --domain superset --format jed1.x, used by Superset 5.
Only displayed text changes; SQL identifiers and locale option values are untouched.
"""
import hashlib,json,re
from pathlib import Path
from collections import Counter
from babel.messages.pofile import read_po,write_po
from babel.messages.mofile import write_mo
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'vendor/superset-5.0.0-fr.po'
EXPECTED='d109e9974d47881f054e01110cc851fe8865c0030d682f2bdd4597410de71422'
TOKEN=re.compile(r'%(?:\([^)]+\))?(?:\d+\$)?(?:\.\d+)?[sdfir]')
def tokens(value):return Counter(TOKEN.findall(value.replace('%%','')))
def format_valid(message):
 ids=message.id if isinstance(message.id,(tuple,list)) else (message.id,)
 strings=message.string if isinstance(message.string,(tuple,list)) else (message.string,)
 return all(not s or tokens(s)==tokens(ids[min(i,len(ids)-1)]) for i,s in enumerate(strings))
def compile_catalog():
 assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==EXPECTED,'Official source hash differs'
 with SOURCE.open('rb') as f:catalog=read_po(f,locale='fr')
 overrides=json.loads((ROOT/'fr-overrides.json').read_text())
 for msgid,value in overrides.items():
  message=catalog.get(msgid)
  if message is None:message=catalog.add(msgid,value)
  else:message.string=value;message.flags.discard('fuzzy')
  assert format_valid(message) and not message.check(catalog),('Override format',msgid)
 skipped=[];entries={}
 for message in catalog:
  if not message.id:continue
  if 'fuzzy' in message.flags or not message.string:continue
  if not format_valid(message) or message.check(catalog):
   skipped.append(message.id);message.string=tuple('' for _ in message.string) if isinstance(message.string,(tuple,list)) else '';continue
  original=message.id[0] if isinstance(message.id,(tuple,list)) else message.id
  key=(message.context+'\x04' if message.context else '')+original
  translated=list(message.string) if isinstance(message.string,(tuple,list)) else [message.string]
  if any(translated):entries[key]=translated
 pack={'domain':'superset','locale_data':{'superset':{'':{'domain':'superset','plural_forms':'nplurals=2; plural=(n > 1);','lang':'fr'},**entries}}}
 target=ROOT/'build/fr/LC_MESSAGES';target.mkdir(parents=True,exist_ok=True)
 with (target/'messages.mo').open('wb') as f:write_mo(f,catalog,use_fuzzy=False)
 with (target/'messages.po').open('wb') as f:write_po(f,catalog,width=100)
 (target/'messages.json').write_text(json.dumps(pack,ensure_ascii=False,separators=(',',':'))+'\n')
 report={'version':'5.0.0','source_sha256':EXPECTED,'translated_entries':len(entries),'reviewed_overrides':len(overrides),'invalid_upstream_entries_skipped':skipped}
 (ROOT/'build/report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 # Test the actual backend binary and the frontend dictionary with format substitutions.
 import gettext
 with (target/'messages.mo').open('rb') as f:translation=gettext.GNUTranslations(f)
 for k in ['Dashboards','Apply filters','Download','Published','Draft']:
  assert translation.gettext(k)==overrides[k]==entries[k][0]
 assert (entries['Applied filters (%s)'][0] % '2')=='Filtres appliqués (2)'
 print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':compile_catalog()
