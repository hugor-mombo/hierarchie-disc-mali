"""Ajout idempotent du socle commun aux deux dashboards publiés, sans les reconstruire.

À exécuter après les provisionnements ASC / SD. Les autres dashboards (dont ASA)
restent inchangés. Aucun changement de comptes ou d'habilitations existantes.
"""
import json
from pathlib import Path
from superset.app import create_app
ROOT=Path(__file__).resolve().parent
from site_registry_catalog import uid,PREFIX,METRICS,COLUMNS,LEGACY_DATASETS
METHOD='''### Un même référentiel pour lire les tableaux ASC et SD
**Sites DISC** : inventaire courant du portefeuille SD, qu’un contact ASC soit présent ou non. Les sites créés après le mois sont exclus du compteur ; une date inconnue reste incluse provisoirement et signalée. Ce n’est pas un historique des ouvertures / fermetures.
**Contact ASC éligible** : appartenance au relevé analytique ASC et création antérieure à la fin du mois. Cette présence ne certifie ni un compte actif ni un site fonctionnel. **Rapporteur ASC** : au moins un rapport attribué dans cette cohorte ; les rapports des sites hors cohorte ne sont pas audités par ce compteur. **Visité SD** : au moins une visite avec ASC (`visit_chw_site`) déclarée sur le site dans la période, distinct du quota complet.
Les quatre compteurs sont dédupliqués par UUID dans la période choisie et partagent la géographie courante. Sur plusieurs mois, un site est compté une seule fois ; les lignes d’export restent des sites-mois. Aucun statut « fermé DHIS2 » n’est déduit de l’absence de contact ou de rapport.
**Écarts** : les motifs reflètent les règles du relevé ASC (contact absent, formation, nom zz / NE, etc.). Ces règles ne suppriment aucune structure DISC. Les sites sans contact restent dans l’inventaire et le dénominateur SD ; cela ne démontre pas qu’un quota de supervision leur est applicable. Le taux SD décrit le portefeuille, pas une obligation individuelle vérifiée.
**Sources et fraîcheur** : la date du portefeuille, le calcul du registre et celui des rapports sont affichés séparément. Rafraîchir le registre ne rafraîchit pas les relevés amont. Les données SD ne sont disponibles que pour les mois préparés par la source : un compteur sans données s’affiche sans valeur, pas comme une activité nulle. Le mois en cours est incomplet.
**Exports** : menu ⋮ du tableau → Télécharger → CSV / XLSX. Le statut du site et le motif ASC expliquent l’écart pour chaque mois. Les filtres de situation / motif ne portent que sur ces tableaux, afin de conserver les dénominateurs des cartes.
'''
app=create_app()
with app.test_request_context('/'):
 from flask import g
 from flask_login import login_user
 from superset import db,security_manager as sm
 from superset.connectors.sqla.models import SqlaTable,TableColumn,SqlMetric
 from superset.models.dashboard import Dashboard
 from superset.models.slice import Slice
 from regional_security import apply_regional_security
 owner=sm.find_user(username='hmombo');assert owner
 login_user(owner);g.user=owner
 ds=db.session.query(SqlaTable).filter_by(uuid=uid('dataset')).one_or_none()
 if ds is None:
  ds=SqlaTable(uuid=uid('dataset'),database_id=1,schema='public',table_name='DISC — Référentiel commun sites ASC et SD');db.session.add(ds)
 ds.sql=(ROOT/'sql/site-registry/monthly.sql').read_text();ds.main_dttm_col='reported_month';ds.owners=[owner];ds.created_by=ds.changed_by=owner;ds.description=METHOD
 for name,kind,label in COLUMNS:
  col=next((x for x in ds.columns if x.column_name==name),None)
  if col is None:col=TableColumn(column_name=name);ds.columns.append(col)
  col.type=kind;col.verbose_name=label;col.is_dttm=kind.startswith(('DATE','TIMESTAMP'));col.groupby=col.filterable=True
 for name,label,expression in METRICS:
  metric=next((x for x in ds.metrics if x.metric_name==name),None)
  if metric is None:metric=SqlMetric(metric_name=name);ds.metrics.append(metric)
  metric.verbose_name=label;metric.expression=expression
 db.session.flush();apply_regional_security([ds])
 untouched={d.id:(d.position_json,d.json_metadata,d.published,d.slug,tuple(sorted(c.id for c in d.slices)))
  for d in db.session.query(Dashboard).all() if d.slug not in ['asc-pilotage','sd-pilotage-disc']}
 reports=[]
 for slug,sql_file in [('asc-pilotage','sites_monthly.sql'),('sd-pilotage-disc','supervision/disc_sites.sql')]:
  dash=db.session.query(Dashboard).filter_by(slug=slug).one()
  legacy=db.session.query(SqlaTable).filter_by(uuid=LEGACY_DATASETS[slug]).one();legacy_id=legacy.id
  assert legacy.database_id==1
  legacy.sql=(ROOT/'sql'/sql_file).read_text()
  site_metric=next(m for m in legacy.metrics if m.metric_name=='sites')
  site_metric.verbose_name='Sites de la cohorte analytique ASC' if slug=='asc-pilotage' else 'Sites DISC · création prise en compte'
  layout=json.loads(dash.position_json);meta=json.loads(dash.json_metadata)
  # Supprimer uniquement les nœuds et filtres créés par ce script.
  for key in list(layout):
   if key.startswith(PREFIX):del layout[key]
  for node in layout.values():
   if isinstance(node,dict) and 'children' in node:node['children']=[k for k in node['children'] if not k.startswith(PREFIX)]
  tabs=next(k for k,v in layout.items() if isinstance(v,dict) and v.get('type')=='TABS' and v.get('parents')==['ROOT_ID','GRID_ID'])
  overview=layout[tabs]['children'][0];charts=[];chart_keys={}
  def chart(key,title,viz,**opts):
   c=db.session.query(Slice).filter_by(uuid=uid(slug+':'+key)).one_or_none()
   if c is None:c=Slice(uuid=uid(slug+':'+key));db.session.add(c)
   c.slice_name=title;c.viz_type=viz;c.datasource_type='table';c.datasource_id=ds.id;c.owners=[owner];c.created_by=c.changed_by=owner
   form=dict(datasource=f'{ds.id}__table',viz_type=viz,granularity_sqla='reported_month',time_range='previous calendar month',adhoc_filters=[],extra_form_data={},row_limit=100000)
   form.update(opts);c.params=json.dumps(form,ensure_ascii=False);c.query_context=None;db.session.flush();charts.append(c);chart_keys[key]=c;return c
  def row(tab,key,items,height):
   rid=PREFIX+slug+'-ROW-'+key;parents=layout[tab]['parents']+[tab]
   layout[tab]['children'].append(rid);layout[rid]=dict(id=rid,type='ROW',children=[],parents=parents,meta={'background':'BACKGROUND_TRANSPARENT'})
   for key,width in items:
    c=chart_keys[key];cid=PREFIX+slug+'-CHART-'+key;layout[rid]['children'].append(cid)
    layout[cid]=dict(id=cid,type='CHART',children=[],parents=parents+[rid],meta=dict(chartId=c.id,sliceName=c.slice_name,uuid=str(c.uuid),width=width,height=height))
  def note(tab,key,code,height):
   rid=PREFIX+slug+'-NOTE-'+key;mid=rid+'-TEXT';parents=layout[tab]['parents']+[tab]
   layout[tab]['children'].append(rid);layout[rid]=dict(id=rid,type='ROW',children=[mid],parents=parents,meta={'background':'BACKGROUND_TRANSPARENT'})
   layout[mid]=dict(id=mid,type='MARKDOWN',children=[],parents=parents+[rid],meta={'code':code,'width':12,'height':height})
  previous=list(layout[overview]['children']);layout[overview]['children']=[]
  note(overview,'intro','''### Référentiel commun des sites ASC / SD
Ces quatre compteurs utilisent **la même période et la même géographie** dans les deux tableaux. « Contact éligible » décrit la cohorte analytique ASC, sans certifier un site fonctionnel. Les rapports concernent cette cohorte. Retrouvez les motifs et les listes exportables dans **Référentiel et écarts**.''',22)
  for key,title,sub in [
   ('inventory','Sites DISC · référentiel commun','Inventaire courant, création prise en compte'),
   ('eligible','Sites avec contact ASC éligible','Cohorte analytique ASC, pas comptes actifs'),
   ('reporters','Sites rapporteurs · cohorte ASC','Au moins un rapport attribué sur la période'),
   ('visited','Sites visités par les SD','Au moins une visite avec ASC déclarée')]:
   chart(key,title,'big_number_total',metric=key,subheader=sub,y_axis_format=',d',header_font_size=.4,subheader_font_size=.12)
  row(overview,'counters',[(k,3) for k in ['inventory','eligible','reporters','visited']],26)
  layout[overview]['children']+=previous
  tab=PREFIX+slug+'-TAB';layout[tabs]['children'].append(tab)
  layout[tab]=dict(id=tab,type='TAB',children=[],parents=['ROOT_ID','GRID_ID',tabs],meta={'text':'Référentiel et écarts'})
  note(tab,'method',METHOD,88)
  table=dict(query_mode='aggregate',all_columns=[],page_length=20,server_page_length=20,server_pagination=True,allow_render_html=False,show_cell_bars=False,table_timestamp_format='%d/%m/%Y')
  chart('summary','Pourquoi les périmètres diffèrent-ils ?', 'table',groupby=['scope_status','contact_status'],metrics=['listed'],**table)
  chart('territories','Référentiel commun — région, district et CSCOM','table',groupby=['region','district','cscom'],metrics=['inventory','eligible','reporters','visited'],**table)
  cols=['reported_month','region','region_uuid','district','district_uuid','cscom','health_area_uuid','zone_name','supervisor_area_uuid','site_name','site_uuid','site_created_date','asc_site_created_date','scope_status','contact_status','contact_count','training_contacts','name_flag','in_period','asc_in_period','asc_report_count','sd_visited','sd_available']
  chart('export','EXPORT — sites et explication des écarts ASC / SD','table',groupby=cols,metrics=[],**{**table,'server_pagination':False})
  chart('freshness','Fraîcheur des relevés communs','table',groupby=['portfolio_snapshot_date','calculated_at','reports_calculated_at'],metrics=['listed'],**table)
  row(tab,'summary',[('summary',12)],44);row(tab,'territories',[('territories',12)],56);row(tab,'export',[('export',12)],64);row(tab,'freshness',[('freshness',12)],25)
  filters=[f for f in meta.get('native_filter_configuration',[]) if not f['id'].startswith(PREFIX)]
  list_ids=[chart_keys[k].id for k in ['summary','export']]
  for f in filters:
   # Statut quota SD : laisser les nouvelles cartes et tables hors de ce filtre.
   target=f.get('targets',[{}])[0].get('column',{}).get('name')
   if target in ['region','district','cscom','zone']:
    f['targets']=[{'datasetId':ds.id,'column':{'name':target}}]
   if target=='quota_status':f['scope']['excluded']=list(set(f['scope'].get('excluded',[])+[c.id for c in charts]))
  for col,label in [('scope_status','Situation du site · listes communes'),('contact_status','Motif ASC · listes communes')]:
   filters.append(dict(id=PREFIX+slug+'-'+col,type='NATIVE_FILTER',name=label,filterType='filter_select',targets=[{'datasetId':ds.id,'column':{'name':col}}],
    controlValues=dict(enableEmptyFilter=False,defaultToFirstItem=False,multiSelect=True,searchAllOptions=True,inverseSelection=False),
    defaultDataMask={'extraFormData':{},'filterState':{},'ownState':{}},cascadeParentIds=[],
    scope={'rootPath':['ROOT_ID'],'excluded':[c.id for c in list(dash.slices)+charts if c.id not in list_ids]},description='Limite les listes communes ; conserve les dénominateurs des cartes.'))
  own_ids={c.id for c in charts}
  old=[c for c in dash.slices if c.id not in own_ids]
  # Libellés explicites pour les anciens compteurs désormais placés après le socle commun.
  for c in old:
   if c.viz_type!='big_number_total' or c.datasource_id!=legacy_id:continue
   form=json.loads(c.params)
   if slug=='asc-pilotage' and form.get('metric')=='sites':
    c.slice_name='Sites de la cohorte analytique ASC';form['subheader']='Contact ASC éligible et création antérieure à la fin du mois'
   if slug=='sd-pilotage-disc' and form.get('metric')=='sites':
    c.slice_name='Sites DISC · périmètre du quota';form['subheader']='Inventaire commun, création prise en compte'
   c.params=json.dumps(form,ensure_ascii=False);c.query_context=None
   for node in layout.values():
    if isinstance(node,dict) and node.get('meta',{}).get('chartId')==c.id:node['meta']['sliceName']=c.slice_name
  # Corriger la description précédente de la grille SD (qui ignorait les créations).
  if slug=='sd-pilotage-disc':
   for node in layout.values():
    if not isinstance(node,dict) or node.get('type')!='MARKDOWN':continue
    code=node.get('meta',{}).get('code','')
    code=code.replace('Les sites créés ou déployés après un mois ancien peuvent apparaître dans cette grille actuelle : ne pas utiliser sa courbe comme un taux de déploiement historique.', 'Les créations postérieures au mois sont exclues. Les déploiements, fermetures et affectations passées ne sont pas reconstitués : ce n’est pas un taux de couverture historique.')
    node['meta']['code']=code
  meta['native_filter_configuration']=filters
  dash.slices=old+charts;dash.position_json=json.dumps(layout,ensure_ascii=False);dash.json_metadata=json.dumps(meta,ensure_ascii=False)
  reports.append({'dashboard':slug,'dataset':ds.id,'charts':{k:c.id for k,c in chart_keys.items()}})
 for d in db.session.query(Dashboard).all():
  if d.id in untouched:assert untouched[d.id]==(d.position_json,d.json_metadata,d.published,d.slug,tuple(sorted(c.id for c in d.slices))),'Unrelated dashboard changed'
 db.session.commit();print(json.dumps({'status':'OK','updated':reports},ensure_ascii=False),flush=True)
