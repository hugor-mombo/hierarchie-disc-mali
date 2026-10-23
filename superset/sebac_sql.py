"""SEBAC report activity and notification cohorts; no patient identity is projected."""
from pathlib import Path
from uuid import UUID,uuid5
ROOT=Path(__file__).resolve().parent
NS=UUID('94708995-d887-4c24-a6dc-24db926c93cd')
def uid(key):return uuid5(NS,key)
TABLES={'reports':'mv_sebac_reports_v1','alerts':'mv_sebac_alerts_v1','sites':'mv_sebac_sites_v1'}
FORMS={
 'sebac_detection':'Détection', 'sebac_alert_notification':'Notification initiale',
 'sebac_alert_sort':'Tri de l’alerte', 'sebac_alert_sort_not_done':'Tri non réalisé déclaré',
 'sebac_alert_verification':'Vérification DTC', 'sebac_verification_notification':'Notification de vérification',
 'sebac_verification_result':'Retour de vérification', 'sebac_test_result_reminder':'Rappel de résultat',
 'sebac_test_result':'Résultat de test', 'sebac_result_notification_supervisor':'Résultat transmis au SD',
 'sebac_result_notification_chw':'Résultat transmis à l’ASC','sebac_alert_notification_dtc':'Notification au DTC'}
def sql(key):return (ROOT/'sql/sebac'/(key+'.sql')).read_text()
