'use client';
import {dhisSiteCounts} from '../lib/site-mappings.mjs';
export default function DhisSiteCounts({snapshot}:any){
 const counts=dhisSiteCounts(snapshot);
 return <section className="panel move-card" aria-label="Statut des sites ASC DHIS2"><h3>Sites ASC dans DHIS2</h3><p><b>{counts.open.toLocaleString('fr-FR')} ouverts</b> · <b>{counts.closed.toLocaleString('fr-FR')} fermés</b> · {counts.total.toLocaleString('fr-FR')} au total{counts.unknown>0&&<> · {counts.unknown.toLocaleString('fr-FR')} au statut inconnu</>}</p><p>Les sites fermés sont exclus du fichier de mappage. Les nombres concernent les UO de niveau 6 du groupe Sites ASC, selon leur date de fermeture dans DHIS2.{counts.scheduled>0&&<> {counts.scheduled} sites ouverts ont une fermeture prévue à une date future.</>}{counts.unknown>0&&<> Les sites au statut inconnu sont exclus jusqu’à vérification.</>}</p>{snapshot?.updatedAt&&<small>Dernière lecture : {new Date(snapshot.updatedAt).toLocaleString('fr-FR',{timeZone:'Africa/Bamako'})}</small>}</section>;
}
