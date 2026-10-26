"""Définitions communes du référentiel ASC / SD."""
from uuid import UUID,uuid5
NS=UUID('07c165d2-f139-45b7-b36e-d001b859f7be')
def uid(key):return uuid5(NS,key)
PREFIX='SITE-REGISTRY-'
METRICS=[
 ('inventory','Sites DISC · référentiel commun','COUNT(DISTINCT CASE WHEN in_period=1 THEN site_uuid END)'),
 ('eligible','Sites avec contact ASC éligible','COUNT(DISTINCT CASE WHEN in_period=1 AND asc_in_period=1 THEN site_uuid END)'),
 ('reporters','Sites rapporteurs · cohorte ASC','COUNT(DISTINCT CASE WHEN in_period=1 AND asc_in_period=1 AND asc_report_count>0 THEN site_uuid END)'),
 ('visited','Sites visités par les SD',"CASE WHEN SUM(sd_available)=0 THEN NULL ELSE COUNT(DISTINCT CASE WHEN in_period=1 AND sd_visited=1 THEN site_uuid END) END"),
 ('listed','Sites listés','COUNT(DISTINCT site_uuid)'),
]
COLUMNS=[(k,'TEXT',v) for k,v in [
 ('region_uuid','Identifiant région'),('region','Région'),('district_uuid','Identifiant district'),('district_name','District'),('district','District · Région'),
 ('health_area_uuid','Identifiant CSCOM'),('cscom_name','CSCOM'),('cscom','CSCOM · District · Région'),('supervisor_area_uuid','Identifiant zone'),('zone_name','Zone'),('zone','Zone · Territoire'),
 ('site_uuid','Identifiant site DISC'),('site_name','Site ASC'),('contact_status','Motif de présence / exclusion ASC'),('scope_status','Situation du site pour le mois')]]+[
 ('reported_month','DATE','Mois'),('site_created_date','DATE','Création du site · relevé courant'),('asc_site_created_date','DATE','Création retenue par la cohorte ASC'),
 ('portfolio_snapshot_date','DATE','Date du portefeuille SD'),('calculated_at','TIMESTAMP WITH TIME ZONE','Calcul du registre commun'),('reports_calculated_at','TIMESTAMP WITH TIME ZONE','Calcul des rapports ASC')]+[
 (k,'BIGINT',v) for k,v in [('has_eligible_asc','Présent dans la cohorte ASC actuelle'),('asc_in_period','Éligible ASC pour le mois'),('in_period','Inclus dans l’inventaire du mois'),('contact_count','Contacts ASC rattachés'),('training_contacts','Contacts de formation · hors cohorte'),('missing_username_contacts','Contacts sans identifiant · hors cohorte'),('name_flag','Nom à examiner (zz / NE)'),('asc_report_count','Rapports attribués · cohorte ASC'),('sd_visited','Visite avec ASC déclarée par un SD'),('sd_available','Relevé SD disponible pour le site-mois')]]

LEGACY_DATASETS={
 'asc-pilotage':uuid5(UUID('57827c7a-4258-4364-bb34-42e237772808'),'sites'),
 'sd-pilotage-disc':uuid5(UUID('b5c4c943-b6a0-4215-87ef-80c45be3b396'),'dataset:disc'),
}
