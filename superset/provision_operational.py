"""Lot 2 : listes opérationnelles et exports. Exécution dans superset_app."""
import argparse
import json
from pathlib import Path
from uuid import UUID, uuid5
from superset.app import create_app

ROOT = Path(__file__).resolve().parent
NAMESPACE = UUID('a88972a5-b85f-4772-92cf-8ff98e473283')
parser = argparse.ArgumentParser()
parser.add_argument('--publish', action='store_true')
args = parser.parse_args()


def uid(key):
    return uuid5(NAMESPACE, key)


app = create_app()
with app.test_request_context('/'):
    from flask import g
    from flask_login import login_user
    from superset import db
    from superset.connectors.sqla.models import SqlaTable, SqlMetric, TableColumn
    from superset.models.dashboard import Dashboard
    from superset.models.slice import Slice
    owner = app.appbuilder.sm.find_user(username='hmombo')
    assert owner is not None
    g.user = owner
    login_user(owner)

    geo_columns = [
        ('region','TEXT','Région'), ('district','TEXT','District · Région'),
        ('cscom','TEXT','CSCOM · District · Région'), ('site','TEXT','Site (identifiant court)'),
        ('region_uuid','TEXT','Identifiant région'), ('district_uuid','TEXT','Identifiant district'),
        ('health_area_uuid','TEXT','Identifiant CSCOM'), ('site_uuid','TEXT','Identifiant site'),
        ('district_name','TEXT','District'), ('cscom_name','TEXT','CSCOM'),
        ('supervision_area','TEXT','Zone de supervision'), ('site_name','TEXT','Site ASC'),
    ]

    def dataset(key, title, sql, columns, metrics):
        obj = db.session.query(SqlaTable).filter_by(uuid=uid(key)).one_or_none()
        if obj is None:
            obj = SqlaTable(uuid=uid(key),table_name=title,database_id=1,schema='public')
            db.session.add(obj)
        obj.sql = sql
        obj.main_dttm_col = None
        obj.description = 'Listes de suivi au dernier calcul ; données individuelles selon les droits ASC existants.'
        obj.owners = [owner]
        obj.created_by = owner
        obj.changed_by = owner
        known = {x.column_name:x for x in obj.columns}
        for name, kind, label in columns:
            col = known.get(name)
            if col is None:
                col = TableColumn(column_name=name)
                obj.columns.append(col)
            col.type, col.verbose_name = kind, label
            col.is_dttm = kind.startswith(('DATE','TIMESTAMP'))
            col.filterable = col.groupby = True
        known_metrics = {x.metric_name:x for x in obj.metrics}
        for name, label, expression in metrics:
            m = known_metrics.get(name)
            if m is None:
                m = SqlMetric(metric_name=name)
                obj.metrics.append(m)
            m.verbose_name,m.expression = label,expression
        db.session.flush()
        return obj

    account_columns = geo_columns + [
        ('username','TEXT','Compte ASC'), ('contact_uuid','TEXT','Identifiant contact ASC'),
        ('asc_name','TEXT','Nom ASC'), ('phone','TEXT','Téléphone ASC'),
        ('last_personal_report','TIMESTAMP','Dernier rapport personnel déclaré'),
        ('last_site_report','TIMESTAMP','Dernier rapport déclaré du site'),
        ('days_without_report','INTEGER','Jours sans rapport personnel'),
        ('threshold_days','INTEGER','Seuil de relance (jours)'),
        ('reason','TEXT','Motif de sélection'), ('action_status','TEXT','Suite proposée'),
        ('contact_status','TEXT','Contrôle du rattachement'),
        ('reference_date','DATE','Date de référence'), ('refreshed_at','TIMESTAMP WITH TIME ZONE','Calcul actualisé (UTC)'),
    ]
    accounts = dataset('accounts','ASC — Relances et exports', (ROOT/'sql/ops_accounts.sql').read_text(),
        account_columns,[('accounts','Comptes ASC sélectionnés','COUNT(DISTINCT username)'),
            ('sites','Sites concernés','COUNT(DISTINCT site_uuid)'),
            ('no_personal','Sans rapport personnel retrouvé',"COUNT(DISTINCT CASE WHEN last_personal_report IS NULL THEN username END)"),
            ('refresh','Calcul actualisé (UTC)','MAX(refreshed_at)')])
    child_columns = geo_columns + [
        ('patient_uuid','TEXT','Identifiant enfant DISC'), ('child_name','TEXT','Nom de l’enfant'),
        ('sex','TEXT','Sexe'), ('age_months','INTEGER','Âge au calcul (mois)'),
        ('age_group','TEXT','Tranche d’âge au calcul'),
        ('last_observation','TIMESTAMP','Dernière observation déclarée'),
        ('observation_age_days','INTEGER','Ancienneté de l’observation (jours)'),
        ('observation_recency','TEXT','Ancienneté du signalement'),
        ('source_form','TEXT','Formulaire source'),
        ('latest_penta1','TEXT','Dernière déclaration Penta 1'),
        ('last_negative_assessment','TIMESTAMP','Dernière évaluation déclarant Penta 1 non reçu'),
        ('followup_status','TEXT','Motif de suivi'),
        ('reference_date','DATE','Date de référence'), ('refreshed_at','TIMESTAMP WITH TIME ZONE','Calcul actualisé (UTC)'),
    ]
    children = dataset('children','Enfants signalés zéro dose — Suivi', (ROOT/'sql/ops_children.sql').read_text(),
        child_columns,[('children','Enfants sélectionnés','COUNT(DISTINCT patient_uuid)'),
            ('areas','CSCOM concernés','COUNT(DISTINCT health_area_uuid)'),
            ('old','Observations de 90 jours ou plus',"COUNT(DISTINCT CASE WHEN observation_age_days>=90 THEN patient_uuid END)"),
            ('refresh','Calcul actualisé (UTC)','MAX(refreshed_at)')])
    geography = dataset('geography','Périmètre des listes opérationnelles',
        'SELECT * FROM public.mv_asc_ops_geography',geo_columns,
        [('sites','Sites dans le relevé géographique','COUNT(DISTINCT site_uuid)')])
    from regional_security import apply_regional_security
    apply_regional_security([accounts, children, geography])

    charts = {}

    def chart(key, title, ds, viz='table', **settings):
        obj = db.session.query(Slice).filter_by(uuid=uid('chart:'+key)).one_or_none()
        if obj is None:
            obj = Slice(uuid=uid('chart:'+key))
            db.session.add(obj)
        obj.slice_name,obj.viz_type = title,viz
        obj.datasource_type,obj.datasource_id = 'table',ds.id
        obj.owners = [owner]
        obj.created_by = obj.changed_by = owner
        params = dict(datasource=f'{ds.id}__table',viz_type=viz,time_range='No filter',
            adhoc_filters=[],extra_form_data={},row_limit=100000)
        params.update(settings)
        obj.params = json.dumps(params,ensure_ascii=False)
        obj.query_context = None
        db.session.flush()
        charts[key] = obj
        return obj

    for prefix, ds, cards in [
        ('asc',accounts,[('accounts','Comptes ASC sélectionnés'),('sites','Sites concernés'),('no_personal','Sans rapport personnel retrouvé')]),
        ('child',children,[('children','Enfants sélectionnés'),('areas','CSCOM concernés'),('old','Signalements de 90 jours ou plus')]),
    ]:
        for metric,title in cards:
            chart(prefix+'_'+metric,title,ds,'big_number_total',metric=metric,
                header_font_size=0.45,subheader_font_size=0.14,y_axis_format=',d',
                subheader='Selon les filtres appliqués à cet onglet')

    table_settings = dict(query_mode='aggregate',metrics=[],all_columns=[],
        server_pagination=True,server_page_length=20,page_length=20,
        allow_render_html=False,include_search=False,show_cell_bars=False,
        table_timestamp_format='%d/%m/%Y',order_desc=True,
        column_config={'days_without_report':{'d3NumberFormat':',d'},
                       'age_months':{'d3NumberFormat':',d'},
                       'observation_age_days':{'d3NumberFormat':',d'}})
    account_list = ['cscom','site_name','asc_name','username','phone',
                    'last_personal_report','days_without_report','reason','contact_status']
    child_list = ['cscom','site_name','child_name','age_months','last_observation',
                  'observation_age_days','followup_status','patient_uuid']
    account_export = ['region','district_name','cscom_name','supervision_area','site_name','site_uuid',
        'asc_name','username','contact_uuid','phone','last_personal_report','days_without_report',
        'last_site_report','threshold_days','reason','action_status','contact_status','reference_date','refreshed_at']
    child_export = ['region','district_name','cscom_name','supervision_area','site_name','site_uuid',
        'child_name','patient_uuid','sex','age_months','age_group','last_observation','observation_age_days',
        'latest_penta1','last_negative_assessment','followup_status','reference_date','refreshed_at']
    for key,title,ds,cols in [
        ('asc_list','ASC — Liste de relance',accounts,account_list),
        ('asc_export','EXPORT ASC — Liste complète avec arborescence',accounts,account_export),
        ('child_list','Enfants — Liste de suivi',children,child_list),
        ('child_export','EXPORT ENFANTS — Liste complète avec arborescence',children,child_export),
    ]:
        options=dict(table_settings)
        if key.endswith('_export'):
            # Pagination d'affichage seulement : l'export conserve la sélection complète.
            options['server_pagination']=False
        chart(key,title,ds,groupby=cols,**options)
    for key,ds in [('asc_freshness',accounts),('child_freshness',children)]:
        chart(key,'Date du calcul opérationnel (UTC)',ds,query_mode='aggregate',
            groupby=[],metrics=['refresh'],row_limit=1,page_length=1,
            table_timestamp_format='%d/%m/%Y %H:%M')
    chart('geography','Périmètre géographique chargé',geography,'big_number_total',metric='sites',
        y_axis_format=',d',header_font_size=0.45,subheader='Sites du relevé courant ; ne signifie pas sites ouverts')

    dash = db.session.query(Dashboard).filter_by(uuid=uid('dashboard')).one_or_none()
    if dash is None:
        dash = Dashboard(uuid=uid('dashboard'),slug='asc-suivi-operationnel')
        db.session.add(dash)
    dash.dashboard_title = 'ASC — Suivi opérationnel et exports'
    dash.owners = [owner]
    dash.created_by = dash.changed_by = owner
    dash.roles = list(db.session.query(Dashboard).filter_by(id=1).one().roles)
    dash.published = args.publish
    dash.slices = list(charts.values())
    layout = {'DASHBOARD_VERSION_KEY':'v2',
        'ROOT_ID':dict(id='ROOT_ID',type='ROOT',children=['GRID_ID']),
        'GRID_ID':dict(id='GRID_ID',type='GRID',children=['TABS-OPS'],parents=['ROOT_ID']),
        'HEADER_ID':dict(id='HEADER_ID',type='HEADER',meta={'text':dash.dashboard_title}),
        'TABS-OPS':dict(id='TABS-OPS',type='TABS',children=[],parents=['ROOT_ID','GRID_ID'])}

    def tab(key,title):
        tid='TAB-OPS-'+key
        layout['TABS-OPS']['children'].append(tid)
        layout[tid]=dict(id=tid,type='TAB',children=[],parents=['ROOT_ID','GRID_ID','TABS-OPS'],meta={'text':title})
        return tid

    def row(tid,key,items,height):
        rid='ROW-OPS-'+key
        parents=['ROOT_ID','GRID_ID','TABS-OPS',tid]
        layout[tid]['children'].append(rid)
        layout[rid]=dict(id=rid,type='ROW',children=[],parents=parents,meta={'background':'BACKGROUND_TRANSPARENT'})
        for ckey,width in items:
            obj=charts[ckey];cid='CHART-OPS-'+ckey
            layout[rid]['children'].append(cid)
            layout[cid]=dict(id=cid,type='CHART',children=[],parents=parents+[rid],
                meta=dict(chartId=obj.id,sliceName=obj.slice_name,uuid=str(obj.uuid),width=width,height=height))

    def note(tid,key,code,height):
        rid,mid='ROW-OPS-note-'+key,'MARKDOWN-OPS-'+key
        parents=['ROOT_ID','GRID_ID','TABS-OPS',tid]
        layout[tid]['children'].append(rid)
        layout[rid]=dict(id=rid,type='ROW',children=[mid],parents=parents,meta={'background':'BACKGROUND_TRANSPARENT'})
        layout[mid]=dict(id=mid,type='MARKDOWN',children=[],parents=parents+[rid],meta={'code':code,'width':12,'height':height})

    asc=tab('asc','ASC à relancer')
    note(asc,'asc_intro','''## Préparer les relances des ASC
Choisissez la région, le district, le CSCOM et éventuellement le site. Le **seuil est de 30 jours par défaut**, modifiable à 7 ou 14 jours. Cliquez sur **Apply filters** après vos sélections.

Cette liste mesure les **rapports déclarés**, pas la synchronisation du téléphone. Une ligne correspond à un **compte ASC**, identifié par son nom de connexion. La rubrique « À vérifier » distingue les rapports uniquement attribués au site et les rattachements incohérents. [Pilotage national](/superset/dashboard/asc-pilotage-v2/) · [Complétude des tâches](/superset/dashboard/asc-completude-taches/).''',32)
    row(asc,'asc_cards',[('asc_accounts',4),('asc_sites',4),('asc_no_personal',4)],23)
    row(asc,'asc_list',[('asc_list',12)],66)
    note(asc,'asc_export_note','''### Télécharger la liste complète
Le tableau **EXPORT ASC** ci-dessous conserve les colonnes d’arborescence et les identifiants. Ouvrez son menu **⋮ → Download → Export to .CSV** ou **Export to Excel**. L’export correspond aux filtres appliqués, au-delà de la seule page affichée. Conservez le seuil sélectionné pour comparer le nombre de comptes et le fichier exporté.''',18)
    row(asc,'asc_export',[('asc_export',12)],50)
    row(asc,'asc_freshness',[('asc_freshness',12)],14)

    child=tab('children','Enfants signalés zéro dose')
    note(child,'child_intro','''## Retrouver les enfants à réévaluer
La sélection par défaut retient les enfants de **12 à 59 mois au calcul**, avec **Penta 1 déclaré non reçu**, sans preuve positive retrouvée dans les sources contrôlées. Il s’agit de **signalements à confirmer sur le terrain**, pas d’une estimation de couverture vaccinale.

Une seule ligne par identifiant enfant. L’âge vient de la date de naissance disponible ; les âges et localisations incertains restent dans les catégories « À vérifier ». Les observations anciennes sont signalées séparément. Les contacts introuvables, les enfants hors cible, ceux avec Penta 1 reçu enregistré ou un décès renseigné ne sont pas présentés comme enfants à retrouver.''',30)
    row(child,'child_cards',[('child_children',4),('child_areas',4),('child_old',4)],23)
    row(child,'child_list',[('child_list',12)],66)
    note(child,'child_export_note','''### Export pour le suivi terrain
Utilisez le menu **⋮ → Download → Export to .CSV** ou **Export to Excel** du tableau **EXPORT ENFANTS**. Il inclut Région, District, CSCOM, zone de supervision, site, identifiant enfant, âge au calcul, dernière observation et motif de suivi. Les informations nominatives et les fichiers restent réservés aux personnes autorisées au suivi.''',18)
    row(child,'child_export',[('child_export',12)],50)
    row(child,'child_freshness',[('child_freshness',12)],14)

    method=tab('method','Méthode et limites')
    note(method,'method','''## Bien interpréter les listes
**ASC.** Comptes disposant du rôle ASC dans le relevé utilisateur et rattachés à un site du périmètre courant, hors comptes de formation. Un compte peut partager un contact avec un autre compte : le nombre de comptes n’est pas un nombre de personnes. La dernière activité personnelle est le dernier rapport attribué au contact du compte ; les rapports rattachés seulement au site restent distincts. L’absence d’historique personnel ne prouve pas une absence de travail ni une absence de synchronisation.

**Seuil.** Le filtre obligatoire « Seuil ASC (jours) » choisit 7, 14 ou 30 jours, avec une comparaison inclusive. La sélection « À relancer » est proposée par défaut. « À vérifier » regroupe les rattachements différents et les situations sans attribution personnelle alors que le site dispose de rapports récents. Les dates futures sont exclues.

**Enfants.** La dernière observation disponible parmi les suivis longitudinaux, suivis vaccinaux et évaluations est utilisée. Les preuves positives connues du cumul historique jusqu’au mois précédent sont complétées par les derniers formulaires et les rapports du mois courant. Une déclaration ultérieure manquante n’est pas une preuve de non-vaccination. Les signalements à confirmer sont séparés des âges, localisations et informations vaccinales à vérifier.

**Âge et localisation.** L’âge est recalculé à la date du calcul à partir de la date de naissance du contact courant. Les tranches de 12–23 et 24–59 mois peuvent être sélectionnées. La localisation provient du contact courant ; un rattachement au dernier rapport est conservé seulement pour repérer les dossiers « Localisation courante à vérifier ». Les déplacements historiques ne sont pas reconstitués. Le statut ouvert/fermé DHIS2 n’est pas encore relié à ces listes.

**Fraîcheur.** Le calcul opérationnel est actualisé chaque heure à partir des relevés analytiques disponibles. Son horodatage ne prouve pas la fraîcheur de la réplication DISC amont. La situation réelle, une vaccination non encore saisie ou un décès non renseigné peuvent différer du relevé : vérifiez avant d’intervenir.

**Exports.** Appliquez d’abord les filtres, puis téléchargez depuis le tableau EXPORT de l’onglet concerné. La limite technique est de 100 000 lignes ; le contrôle de livraison vérifie que les listes complètes tiennent dans cette limite. Les données nominatives conservent l’audience autorisée du tableau ASC historique.

Référence : [définition opérationnelle zéro dose — OMS](https://www.who.int/data/gho/indicator-metadata-registry/imr-details/7792). La liste est une aide au suivi, pas un indicateur national de prévalence.

[Pilotage national V2](/superset/dashboard/asc-pilotage-v2/) · [ASC historique](/superset/dashboard/1/)''',108)
    row(method,'geography',[('geography',12)],23)

    all_ids=[c.id for c in charts.values()]
    asc_ids=[c.id for k,c in charts.items() if k.startswith('asc_')]
    child_ids=[c.id for k,c in charts.items() if k.startswith('child_')]
    filters=[]

    def select_filter(key,name,ds,col,parents=None,scope=None,default=None,multi=True,required=False):
        state={'extraFormData':{},'filterState':{},'ownState':{}}
        if default is not None:
            state={'extraFormData':{'filters':[{'col':col,'op':'IN','val':default}]},
                   'filterState':{'value':default,'label':', '.join(map(str,default))},'ownState':{}}
        filters.append(dict(id='NATIVE_FILTER-ops-'+key,type='NATIVE_FILTER',name=name,filterType='filter_select',
            targets=[{'datasetId':ds.id,'column':{'name':col}}],
            controlValues=dict(enableEmptyFilter=required,defaultToFirstItem=False,multiSelect=multi,
                               searchAllOptions=True,inverseSelection=False),defaultDataMask=state,
            cascadeParentIds=['NATIVE_FILTER-ops-'+p for p in (parents or [])],
            scope={'rootPath':['ROOT_ID'],'excluded':[i for i in all_ids if scope is not None and i not in scope]},
            description='Sélectionnez une valeur puis appliquez les filtres.'))

    for key,name,parents in [('region','Région',[]),('district','District',['region']),
                             ('cscom','CSCOM',['region','district']),('site','Site ASC',['region','district','cscom'])]:
        select_filter(key,name,geography,key,parents)
    select_filter('threshold','Seuil ASC (jours)',accounts,'threshold_days',scope=asc_ids,default=[30],multi=False,required=True)
    select_filter('asc_status','Suite proposée ASC',accounts,'action_status',scope=asc_ids,default=['À relancer'])
    select_filter('child_status','Motif de suivi enfant',children,'followup_status',scope=child_ids,
                  default=['Penta 1 non reçu déclaré — à confirmer'])
    select_filter('age','Tranche d’âge enfant',children,'age_group',parents=['child_status'],scope=child_ids)
    select_filter('recency','Ancienneté du signalement',children,'observation_recency',
                  parents=['child_status','age'],scope=child_ids)
    dash.position_json=json.dumps(layout,ensure_ascii=False)
    dash.json_metadata=json.dumps(dict(native_filter_configuration=filters,cross_filters_enabled=False,
        refresh_frequency=0,expanded_slices={},timed_refresh_immune_slices=[],
        default_filters='{}',chart_configuration={},color_scheme='supersetColors'),ensure_ascii=False)
    dash.css='''.dashboard-content {background:#f3f6fb;}
.dashboard-component-chart-holder {border:1px solid #e3eaf3;border-radius:10px;}
.dashboard-markdown h2 {color:#153854;}
'''
    db.session.commit()
    print(json.dumps(dict(id=dash.id,slug=dash.slug,published=dash.published,
        datasets={'accounts':accounts.id,'children':children.id,'geography':geography.id},
        charts={k:v.id for k,v in charts.items()},export_columns={'accounts':account_export,'children':child_export}),ensure_ascii=False))
