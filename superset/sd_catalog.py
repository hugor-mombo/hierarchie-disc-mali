"""Lot 1 supervision: native sources remain separate, including native ASA geography."""
from pathlib import Path
from uuid import UUID,uuid5
ROOT=Path(__file__).resolve().parent
NS=UUID('b5c4c943-b6a0-4215-87ef-80c45be3b396')
def uid(key):return uuid5(NS,key)
GEO=[('reported_month','DATE','Mois'),('year','INTEGER','Année'),('region_uuid','TEXT','Identifiant région natif'),('region','TEXT','Région déclarée'),
 ('district_uuid','TEXT','Identifiant district natif'),('district_name','TEXT','District déclaré'),('district','TEXT','District · Région'),
 ('supervisor_area_uuid','TEXT','Identifiant zone natif'),('zone_name','TEXT','Zone de supervision'),('zone','TEXT','Zone · Territoire'),
 ('supervisor_name','TEXT','Superviseur du répertoire courant')]
SOURCES={
 'disc':dict(db=1,title='SD DISC — Sites et quotas mensuels',sql='disc_sites.sql',columns=GEO+[
 ('health_area_uuid','TEXT','Identifiant CSCOM'),('cscom_name','TEXT','CSCOM'),('cscom','TEXT','CSCOM · Territoire'),
 ('site_uuid','TEXT','Identifiant site DISC'),('site_name','TEXT','Site ASC'),('supervisor_uuid','TEXT','Identifiant superviseur'),
 ('assignment_status','TEXT','Code de rattachement superviseur'),('assignment_label','TEXT','Rattachement superviseur'),('quota_status','TEXT','État du quota mensuel'),
 ('last_activity_at','TIMESTAMP WITH TIME ZONE','Dernière activité déclarée du mois')]+[(k,'NUMERIC',v) for k,v in [
 ('site_visits','Visites avec ASC'),('community_visits','Visites sans ASC'),('feedbacks','Entretiens individuels'),('visited','Site-mois avec visite ASC'),('three_forms','Site-mois avec trois formulaires'),('quota','Site-mois au quota'),('missing_site_visits','Visites avec ASC manquantes'),('missing_community_visits','Visites sans ASC manquantes'),('missing_feedbacks','Entretiens manquants')]],metrics=[
 ('sites','Sites distincts du portefeuille courant','COUNT(DISTINCT site_uuid)'),
 ('site_months','Sites-mois du portefeuille courant','COUNT(*)'),
 ('visited_sites','Sites distincts avec visite ASC','COUNT(DISTINCT CASE WHEN visited=1 THEN site_uuid END)'),
 ('visited_months','Sites-mois avec visite ASC','SUM(visited)'),
 ('quota_count','Sites-mois au quota complet','SUM(quota)'),
 ('quota_rate','Part des sites-mois au quota','1.0*SUM(quota)/NULLIF(COUNT(*),0)'),
 ('no_activity','Sites-mois sans les trois formulaires',"COUNT(*) FILTER(WHERE quota_status='Aucun des trois formulaires')"),
 ('incomplete','Sites-mois au quota incomplet','COUNT(*)-SUM(quota)'),
 ('assignment_issues','Sites avec rattachement superviseur à vérifier',"COUNT(DISTINCT CASE WHEN assignment_status<>'assigned' THEN site_uuid END)"),
 ('site_visits','Rapports de visite avec ASC','SUM(site_visits)'),('community_visits','Rapports de visite sans ASC','SUM(community_visits)'),('feedbacks','Rapports d’entretien individuel','SUM(feedbacks)'),
 ('missing_site_visits','Visites avec ASC manquantes','SUM(missing_site_visits)'),('missing_community_visits','Visites sans ASC manquantes','SUM(missing_community_visits)'),('missing_feedbacks','Entretiens manquants','SUM(missing_feedbacks)')]),
 'asa_history':dict(db=2,title='SD ASA — Supervision historique 2019–2025',sql='asa_history.sql',columns=GEO+[
 ('supervisor_contact_id','TEXT','Identifiant superviseur ASA')]+[(k,'NUMERIC',v) for k,v in [
 ('quota_site_months','Sites-mois au quota'),('eligible_site_months','Sites-mois actifs'),('known_site_months','Sites-mois avec état connu'),('visited_site_months','Sites-mois actifs avec visite ASC'),('inactive_quota','Sites-mois inactifs avec quota'),('unknown_creation','Sites-mois sans date de création'),('site_visits','Visites avec ASC'),('community_visits','Visites sans ASC'),('feedbacks','Entretiens individuels')]],metrics=[
 ('eligible','Sites-mois actifs ASA','SUM(eligible_site_months)'),('quota_count','Sites-mois actifs au quota ASA','SUM(quota_site_months)'),
 ('quota_rate','Part des sites-mois actifs au quota ASA','1.0*SUM(quota_site_months)/NULLIF(SUM(eligible_site_months),0)'),
 ('incomplete','Sites-mois actifs hors quota ASA','SUM(eligible_site_months)-SUM(quota_site_months)'),
 ('site_visits','Rapports avec ASC — sites actifs ASA','SUM(site_visits)'),('community_visits','Rapports sans ASC — sites actifs ASA','SUM(community_visits)'),('feedbacks','Entretiens — sites actifs ASA','SUM(feedbacks)'),
 ('inactive_quota','Sites-mois inactifs avec quota','SUM(inactive_quota)'),('unknown_creation','Sites-mois sans création renseignée','SUM(unknown_creation)')]),
 'asa_recent':dict(db=2,title='SD ASA — Indicateurs FM/GAVI disponibles',sql='asa_recent.sql',columns=GEO+[
 ('supervisor_contact_id','TEXT','Identifiant superviseur ASA')]+[(k,'NUMERIC',v) for k,v in [
 ('eligible_site_months','Sites-mois actifs'),('curative_visits','VAD curatives déclarées'),('rdt_done','TDR observés'),('rdt_correct','TDR conformes — définition ASA')]],metrics=[
 ('eligible','Sites-mois actifs ASA','SUM(eligible_site_months)'),('curative_visits','VAD curatives déclarées ASA','SUM(curative_visits)'),
 ('average_visits','VAD curatives / site-mois actif ASA','SUM(curative_visits)/NULLIF(SUM(eligible_site_months),0)'),
 ('rdt_done','TDR observés ASA','SUM(rdt_done)'),('rdt_correct','TDR conformes — définition ASA','SUM(rdt_correct)'),
 ('rdt_rate','Part de TDR conformes — définition ASA','1.0*SUM(rdt_correct)/NULLIF(SUM(rdt_done),0)')])}
FRESHNESS=[('first_month','Premier mois sélectionné','MIN(reported_month)'),('last_month','Dernier mois sélectionné','MAX(reported_month)'),('rows','Lignes de relevé','COUNT(*)')]
def sql(key):return (ROOT/'sql/supervision'/SOURCES[key]['sql']).read_text()
