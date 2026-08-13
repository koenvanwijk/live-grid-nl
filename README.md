# NL Live Grid

Interactieve kaart van het Nederlandse elektriciteitsnet met officiële nettopologie, actuele systeemdata en grote productie-, opslag- en grensassets. De applicatie is een statische PWA en draait op GitHub Pages.

Live: https://koenvanwijk.github.io/live-grid-nl/

## Wat de kaart toont

- **TenneT hoogspanningsnet** vanaf 110 kV: bovengrondse lijnen, kabels en stations uit de openbare ArcGIS FeatureServer.
- **Actuele systeemwaarden**: vraag, productie, productiemix en fysieke grensstromen uit TenneT, NED en ENTSO-E, afhankelijk van de beschikbare API-tokens.
- **Wind op land** uit de landelijke RIVM-dataset `Windturbines – vermogen`. Individuele turbines worden automatisch geclusterd; op overzichtsniveau worden alleen clusters van minimaal 25 MW getoond. Bij verder inzoomen verschijnen individuele turbines met LOD-begrenzing.
- **Wind op zee** met geïnstalleerd vermogen, aanlandingen en waar beschikbaar actuele NED-productie.
- **Zonneparken** uit ROM3D **Zon op Kaart**. Alleen gerealiseerde fysieke parken van minimaal 25 MWp worden gepubliceerd. Meerdere SDE-records op dezelfde locatie worden eerst geaggregeerd. Er wordt geen hectare-naar-MWp-schatting gebruikt.
- **Batterijopslag** vanaf 25 MW uit een kleine handmatig geverifieerde projectset.
- **Grote centrales** voor gas, steenkool, kernenergie en biomassa. De actuele unitproductie is niet publiek beschikbaar; de kaart toont daarom een duidelijk als **afgeleid** gemarkeerde verdeling van landelijke productie over bekende capaciteit.
- **Buitenlandverbindingen** met nominale capaciteit, actuele richting en flow. Duitse marktgrensdata wordt niet voorgesteld als een gemeten verdeling per fysieke corridor.

Alle capaciteitssymbolen gebruiken dezelfde `capacityDiameter(mw)`-schaal. Daardoor krijgt hetzelfde MW-vermogen voor wind, zon, centrale, opslag of interconnector dezelfde visuele diameter; alleen vorm en kleur verschillen.

## Datakwaliteit

De UI gebruikt twee onafhankelijke eigenschappen:

- **Herkomst**: `measured`, `derived`, `modelled`, `static`.
- **Tijd**: `actual`, `forecast`, `none`.

Belangrijk: interne TenneT-SCADA-lijnstromen zijn niet openbaar. De basis-hoogspanningslijnen blijven daarom neutrale assetlijnen. Bewegende flow-indicaties worden alleen gebruikt waar de onderliggende actuele data dat ondersteunt, bijvoorbeeld voor grensstromen en wind op zee.

## Databronnen

| Onderdeel | Bron | Type | Verversing |
|---|---|---|---|
| Hoogspanningslijnen, kabels, stations | TenneT Assets Hoogspanning ArcGIS | statisch/topologie | rechtstreeks in browser |
| Vraag / balans | TenneT API en/of NED | gemeten | Pages workflow, elke 15 min |
| Productiemix en grensstromen | ENTSO-E Transparency Platform | gemeten | Pages workflow, elke 15 min |
| Regionale zon/wind en offshore productie | NED | gemeten | Pages workflow, elke 15 min |
| Wind op land | RIVM `Windturbines – vermogen` | statische capaciteit/geometrie | dagelijks |
| Zonneparken ≥25 MWp | ROM3D Zon op Kaart / ArcGIS | statische capaciteit/geometrie | wekelijks |
| Grote centrales | `data/large-plants.json` | gecureerde statische capaciteit | handmatig |
| Batterijopslag | `data/solar-storage.json` | gecureerde statische capaciteit | handmatig |
| Lands-/provinciegrenzen | PDOK/Kadaster | statische geometrie | rechtstreeks in browser |

TenneT FeatureServer:

`https://services-eu1.arcgis.com/WjozPuR5ROn6NZE8/ArcGIS/rest/services/TenneT_Assets_Hoogspanning/FeatureServer`

Gebruikte lagen: `2` bovengrondse verbindingen, `3` ondergrondse kabels en `5` stations.

## Lokaal installeren

Vereist: **Python 3.12+**. Voor de frontend is geen Node-build nodig.

```bash
git clone https://github.com/koenvanwijk/live-grid-nl.git
cd live-grid-nl
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/check_repo.py
python -m http.server 8080
```

Open daarna `http://localhost:8080`.

De repository bevat reeds snapshots van de gegenereerde datasets. Voor alleen de UI hoef je dus geen API-token te configureren.

## Live data lokaal verversen

De drie tokens zijn onafhankelijk. Configureer alleen de bronnen die je wilt gebruiken:

```bash
export ENTSO_E_TOKEN='...'
export NED_TOKEN='...'
export TENNET_TOKEN='...'
python scripts/update_live.py
python scripts/enrich_provenance.py
python scripts/validate_observations.py
```

- `ENTSO_E_TOKEN`: productiemix, geïnstalleerde capaciteit en fysieke grensstromen.
- `NED_TOKEN`: regionale zon/wind, offshore wind en fallback voor landelijke waarden.
- `TENNET_TOKEN`: TenneT metered-injections en balansinformatie.

Zonder tokens schrijft `update_live.py` bewust geen verzonnen waarden.

## Statische datasets lokaal verversen

Wind op land gebruikt alleen de standaardbibliotheek:

```bash
python scripts/fetch_rivm_wind.py
```

Zonneparken gebruiken `requests` uit `requirements.txt`:

```bash
python scripts/update_solar_parks.py
```

Beide scripts voeren sanity checks uit en weigeren een lege of evident onwaarschijnlijke dataset te publiceren. `python scripts/check_repo.py` controleert daarna de belangrijkste schema- en drempelafspraken in samenhang.

## GitHub Actions

- `pages.yml` — ververst live data en deployt GitHub Pages iedere 15 minuten en na een push naar `main`.
- `update-rivm-wind.yml` — vernieuwt de RIVM-winddataset dagelijks.
- `update-solar-parks.yml` — vernieuwt de ROM3D-zonneparkdataset wekelijks.
- `ci.yml` — draait unit tests en repository-consistentiechecks op push en pull request.

Voor GitHub Pages: **Settings → Pages → Source: GitHub Actions**.

Voor live data kunnen in **Settings → Secrets and variables → Actions** de secrets `ENTSO_E_TOKEN`, `NED_TOKEN` en `TENNET_TOKEN` worden ingesteld.

## Belangrijkste bestanden

```text
index.html                     statische UI en scriptvolgorde
app.js                         TenneT-kaart, live systeemdashboard en basislagen
styles.css                     algemene UI-styling
data/capacity-scale.js         één gedeelde MW→diameter schaal
data/injections.js             grote centrales en afgeleide unitproductie
data/interconnectors.js        fysieke grensverbindingen en capaciteit
data/interconnector-flags.js   vlaggen, flowstatus en grensdetails
data/solar-storage.js          zon, wind op land en batterij-rendering
data/solar-parks.json          gegenereerde ROM3D-zonneparken ≥25 MWp
data/onshore-wind-rivm.json    gegenereerde RIVM-turbines en ≥25 MW clusters
data/solar-storage.json        handmatig geverifieerde batterijopslag
scripts/update_live.py         actuele publieke systeemdata
scripts/fetch_rivm_wind.py     RIVM-wind ingest en clustering
scripts/update_solar_parks.py  ROM3D ArcGIS solar ingest en aggregatie
scripts/check_repo.py          netwerk-vrije consistentiecheck
tests/                         unit tests
```

## Ontwerpregels

1. Geen placeholder-MW of fictieve live data.
2. `measured`, `derived`, `modelled` en `static` worden niet door elkaar gehaald.
3. Geïnstalleerd vermogen en actuele productie zijn verschillende grootheden.
4. Voor kaartobjecten ≥25 MW wordt waar mogelijk een landelijke bron gebruikt in plaats van een handmatige shortlist.
5. Grote objectsets krijgen LOD; duizenden Leaflet/DOM-objecten worden niet continu gerenderd.
6. Capaciteitssymbolen delen één visuele schaal.
7. Een ingest-workflow mag niet groen eindigen met een lege of evident onwaarschijnlijke dataset.
