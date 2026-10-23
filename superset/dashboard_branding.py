"""Shared institutional banner; only dashboard layout and scoped CSS are changed."""
import html,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ASSET='/assets/disc-mali/armoiries-mali-87405e53.png'
ALT='Armoiries de la République du Mali'
ROW='ROW-DISC-INSTITUTION';MARKDOWN='MARKDOWN-DISC-INSTITUTION'
CSS_START='/* DISC institutional banner start */';CSS_END='/* DISC institutional banner end */'
SLUGS={'asc-pilotage','asc-pilotage-v2','asc-suivi-operationnel','asc-completude-taches','asc-thematiques',
 'sd-supervision','sd-pilotage-disc','sd-historique-asa','sd-qualite-disc','sd-qualite-asa',
 'sites-geolocalisation','sd-classement-disc','asc-classement-disc'}
CSS=(ROOT/'branding/banner.css').read_text()
def selected(d):
 return d.id in [1,2,25] or d.slug in SLUGS or (d.slug or '').startswith('asc-theme-')
def source_label(d):
 if d.slug in ['sd-historique-asa','sd-qualite-asa']:return 'ASA-Mali','Historique · Source distincte'
 if d.id==2:return 'DISC / ASA','Tableau historique · Sources distinctes'
 if d.slug=='sd-supervision':return 'DISC / ASA','Deux sources séparées'
 return 'DISC-Mali','Pilotage et aide à la décision'
def banner(d):
 source,scope=source_label(d)
 # No style/class extension is required: native Markdown permits these structural tags.
 return ('<div>\n<img src="'+ASSET+'" alt="'+ALT+'" width="64" height="64" />\n'
  '<div><strong>République du Mali</strong><br /><b>Santé communautaire</b><br />'
  '<span>'+html.escape(d.dashboard_title)+'</span></div>\n'
  '<p><strong>'+source+'</strong><br /><em>'+scope+'</em></p>\n</div>')
def brand_dashboard(d):
 before=json.loads(d.position_json);assert isinstance(before,dict) and before['GRID_ID']['type']=='GRID'
 assert before['GRID_ID']['parents']==['ROOT_ID'],'Unexpected dashboard root'
 layout=json.loads(d.position_json)
 for node in [ROW,MARKDOWN]:
  if node in layout:assert layout[node]['type']==('ROW' if node==ROW else 'MARKDOWN'),'Banner node collision'
 layout['GRID_ID']['children']=[ROW]+[n for n in layout['GRID_ID']['children'] if n!=ROW]
 layout[ROW]=dict(id=ROW,type='ROW',children=[MARKDOWN],parents=['ROOT_ID','GRID_ID'],meta={'background':'BACKGROUND_TRANSPARENT'})
 layout[MARKDOWN]=dict(id=MARKDOWN,type='MARKDOWN',children=[],parents=['ROOT_ID','GRID_ID',ROW],meta=dict(code=banner(d),width=12,height=16))
 # Every pre-existing node and child order is preserved, apart from our own banner.
 original_children=[n for n in before['GRID_ID']['children'] if n!=ROW]
 assert layout['GRID_ID']['children'][1:]==original_children
 for key,value in before.items():
  if key not in [ROW,MARKDOWN,'GRID_ID']:assert layout[key]==value,key
 css=re.sub(re.escape(CSS_START)+r'.*?'+re.escape(CSS_END),'',d.css or '',flags=re.S).rstrip()
 target_css=css+'\n\n'+CSS_START+'\n'+CSS.strip()+'\n'+CSS_END
 target_position=json.dumps(layout,ensure_ascii=False)
 changed=target_position!=d.position_json or target_css!=d.css
 if changed:d.position_json=target_position;d.css=target_css
 return changed

def brand_primary_dashboards(session,ids=None):
 from superset.models.dashboard import Dashboard
 result=[]
 for d in session.query(Dashboard).order_by(Dashboard.id).all():
  if selected(d) and (ids is None or d.id in ids):
   before=(d.json_metadata,d.dashboard_title,d.slug,d.published,sorted(r.id for r in d.roles),sorted(u.id for u in d.owners),sorted(c.id for c in d.slices))
   changed=brand_dashboard(d)
   assert before==(d.json_metadata,d.dashboard_title,d.slug,d.published,sorted(r.id for r in d.roles),sorted(u.id for u in d.owners),sorted(c.id for c in d.slices)),'Functional metadata changed'
   assert not brand_dashboard(d),'Branding must be idempotent'
   result.append(dict(id=d.id,slug=d.slug,changed=changed,source=source_label(d)[0]))
 return result
