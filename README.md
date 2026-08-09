# NL Live Grid

Interactieve kaart van het Nederlandse hoogspanningsnet, geïnspireerd op de live grid-weergave van Energinet.

## Wat werkt

- Officiële openbare **TenneT** topologie rechtstreeks uit de ArcGIS FeatureServer.
- Bovengrondse lijnen, ondergrondse kabels en hoogspanningsstations vanaf 110 kV.
- Filters voor 110 / 150 / 220 / 380 kV.
- Responsive dashboard voor desktop en mobiel.
- Live nationale vraag, opwek en grensstromen uit **ENTSO-E** via een door GitHub Actions gegenereerde `data/live.json` snapshot.
- Automatische verversing en GitHub Pages deployment iedere 15 minuten.
- Geen verzonnen interne MW-waarden: interne TenneT-SCADA-lijnstromen zijn niet openbaar.

## Eenmalige configuratie

### 1. GitHub Pages

Ga in de repository naar **Settings → Pages** en kies **GitHub Actions** als source. De workflow `.github/workflows/pages.yml` publiceert daarna automatisch bij iedere push naar `main` en iedere 15 minuten.

### 2. ENTSO-E token

Maak in **Settings → Secrets and variables → Actions** een repository secret aan:

`ENTSO_E_TOKEN`

De waarde is je ENTSO-E Transparency Platform API security token. Zonder dit secret blijft de TenneT-kaart volledig werken, maar toont het dashboard bewust geen fictieve live systeemwaarden.

## Databronnen

TenneT Assets Hoogspanning ArcGIS FeatureServer:

`https://services-eu1.arcgis.com/WjozPuR5ROn6NZE8/ArcGIS/rest/services/TenneT_Assets_Hoogspanning/FeatureServer`

Gebruikte lagen:

- 2 — bovengrondse hoogspanningsverbindingen
- 3 — ondergrondse hoogspanningskabels
- 5 — hoogspanningsstations

ENTSO-E Transparency Platform API wordt gebruikt voor actual total load, actual generation per production type en physical cross-border flows van Nederland met België, Duitsland/Luxemburg, Groot-Brittannië, Noorwegen en Denemarken.

## Datakwaliteit

De toepassing maakt expliciet onderscheid tussen bronnen. TenneT-topologie is officiële assetdata. De landelijke en grenswaarden zijn gemeten ENTSO-E-data. Interne lijnstromen worden niet weergegeven zolang er geen verdedigbaar state-estimation/power-flow-model beschikbaar is.

## Lokaal draaien

```bash
ENTSO_E_TOKEN=... python3 scripts/update_live.py
python3 -m http.server 8080
```

Open daarna `http://localhost:8080`.

## Volgende technische stap

Voor een Nederlandse equivalent van de Energinet-kaart kan een bus/branch-model worden opgebouwd uit de TenneT-topologie, verrijkt met elektrische parameters en regionale injecties. Daarna kan een DC power flow/state estimation geschatte MW-flow per interne verbinding leveren, waarbij de UI die waarden expliciet als **modelled/estimated** markeert en gemeten grenswaarden als constraints gebruikt.
