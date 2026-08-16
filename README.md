# NL Live Grid

Interactieve kaart van het Nederlandse elektriciteitsnet met officiële nettopologie, actuele systeemdata en grote productie-, opslag- en grensassets. De applicatie is een statische PWA en draait op GitHub Pages.

Live: https://koenvanwijk.github.io/live-grid-nl/

## Wat de kaart toont

- **TenneT hoogspanningsnet** vanaf 110 kV: bovengrondse lijnen, kabels en stations uit de openbare ArcGIS FeatureServer.
- **Actuele systeemwaarden**: vraag, productie, productiemix en fysieke grensstromen uit TenneT, NED en ENTSO-E, afhankelijk van de beschikbare API-tokens.
- **Provinciale hernieuwbare balans**: actuele NED-productie van zon en wind op land wordt per provincie vergeleken met een gemodelleerde provinciale elektriciteitsvraag. Groen betekent dat zon+wind boven het vraagmodel uitkomen; oranje betekent eronder. De route naar een nabij TenneT-station is alleen een visualisatie, geen gemeten fysieke stroom.
- **Wind op land** uit de landelijke RIVM-dataset `Windturbines – vermogen`. Individuele turbines worden automatisch geclusterd; op overzichtsniveau worden alleen clusters van minimaal 25 MW getoond. Bij verder inzoomen verschijnen individuele turbines met LOD-begrenzing.
- **Wind op zee** met geïnstalleerd vermogen, aanlandingen en waar beschikbaar actuele NED-productie.
- **Zonneparken** uit ROM3D **Zon op Kaart**. De ingest publiceert de volledige gerealiseerde set met bruikbaar vermogen. De frontend gebruikt zoom-LOD: landelijk ≥25 MWp, daarna ≥10 MWp, ≥5 MWp, ≥2 MWp en op detailniveau alle beschikbare parken. Meerdere SDE-records op dezelfde fysieke locatie worden eerst geaggregeerd; er wordt geen hectare-naar-MWp-schatting gebruikt.
- **Batterijopslag** vanaf 25 MW uit een kleine handmatig geverifieerde projectset.
- **Grote centrales** voor gas, steenkool, kernenergie en biomassa. De actuele unitproductie is niet publiek beschikbaar; de kaart toont daarom een duidelijk als **afgeleid** gemarkeerde verdeling van landelijke productie over bekende capaciteit.
- **Buitenlandverbindingen** met nominale capaciteit, actuele richting en flow. Duitse marktgrensdata wordt niet voorgesteld als een gemeten verdeling per fysieke corridor.

Alle capaciteitssymbolen gebruiken dezelfde `capacityDiameter(mw)`-schaal. Daardoor krijgt hetzelfde MW-vermogen voor wind, zon, centrale, opslag of interconnector dezelfde visuele diameter; alleen vorm en kleur verschillen.

## Provinciaal vraagmodel

Er is geen publieke live provinciale elektriciteitsvraagreeks die hier als meting wordt gebruikt. Daarom staat het vraagmodel expliciet los van de gemeten provinciale NED-opwek.

De actuele landelijke elektriciteitsvraag wordt over de 12 provincies verdeeld met:

1. **CBS-bevolking per provincie** als basisgewicht (`data/province-demand-model.json`, CBS tabel 71488NED).
2. Een transparant **uurprofiel per dagtype** voor drie modelklassen: `urban`, `mixed` en `industrial`. Deze profielklasse is een aanname, geen provinciale meting.
3. Na toepassing van de uurfactoren worden alle provinciale waarden opnieuw genormaliseerd, zodat op ieder tijdstip exact geldt:

   `som(gemodelleerde provinciale vraag) = actuele landelijke vraag`

De kaart vergelijkt vervolgens per provincie:

`actuele NED zon + actuele NED wind op land - gemodelleerde provinciale vraag`

Dit is dus bewust een **hernieuwbare balans**, geen volledige provinciale vermogensbalans. Gas, kernenergie, biomassa en andere lokale opwek worden hierin niet regionaal toegerekend. Alle aannames staan ook in de UI onder **Datakwaliteit → Aannames provinciaal gebruik**.

## Datakwaliteit

De UI gebruikt twee onafhankelijke eigenschappen:

- **Herkomst**: `measured`, `derived`, `modelled`, `static`.
- **Tijd**: `actual`, `forecast`, `none`.

Interne TenneT-SCADA-lijnstromen en fysieke stromen tussen provincies zijn niet openbaar. De basis-hoogspanningslijnen blijven daarom neutrale assetlijnen. Grensstromen gebruiken gemeten ENTSO-E-data. De provinciale balans combineert gemeten NED-zon/wind met een expliciet gemodelleerde vraag en mag niet als fysieke load-flow worden geïnterpreteerd.

## Databronnen

| Onderdeel | Bron | Type | Verversing |
|---|---|---|---|
| Hoogspanningslijnen, kabels, stations | TenneT Assets Hoogspanning ArcGIS | statisch/topologie | rechtstreeks in browser |
| Vraag / balans | TenneT API en/of NED | gemeten | Pages workflow, elke 15 min |
| Productiemix en grensstromen | ENTSO-E Transparency Platform | gemeten | Pages workflow, elke 15 min |
| Regionale zon/wind en offshore productie | NED | gemeten | Pages workflow, elke 15 min |
| Provinciale vraaggewichten | CBS tabel 71488NED + modelprofielen | gemodelleerd | statisch model |
| Provinciale balansroute | NED + vraagmodel + TenneT topologie | afgeleid/model | browser, met actuele `live.json` |
| Wind op land | RIVM `Windturbines – vermogen` | statische capaciteit/geometrie | dagelijks |
| Zonneparken | ROM3D Zon op Kaart / ArcGIS | statische capaciteit/geometrie | wekelijks |
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

NED publiceert zon en wind op land per provincie. De totale elektriciteitsbelasting (type 59) is landelijk beschikbaar; `province-flow.js` verdeelt die landelijke MW daarom met het transparante model uit `province-demand-model.json`.

## Statische datasets lokaal verversen

Wind op land:

```bash
python scripts/fetch_rivm_wind.py
```

Zonneparken:

```bash
python scripts/update_solar_parks.py
```

De zonne-ingest schrijft de volledige gerealiseerde fysieke parkset naar `data/solar-parks.json`. De grens van 25 MWp is alleen de landelijke overzichtsdrempel in de UI, niet de ingest-drempel.

## GitHub Actions

- `pages.yml` — ververst live data en deployt GitHub Pages iedere 15 minuten en na een push naar `main`.
- `update-rivm-wind.yml` — vernieuwt de RIVM-winddataset dagelijks.
- `update-solar-parks.yml` — vernieuwt de volledige ROM3D-zonneparkdataset wekelijks.
- `ci.yml` — draait unit tests en repository-consistentiechecks op push en pull request.

Voor GitHub Pages: **Settings → Pages → Source: GitHub Actions**.

Voor live data kunnen in **Settings → Secrets and variables → Actions** de secrets `ENTSO_E_TOKEN`, `NED_TOKEN` en `TENNET_TOKEN` worden ingesteld.

## Belangrijkste bestanden

```text
index.html                         statische UI en scriptvolgorde
app.js                             TenneT-kaart, live systeemdashboard en basislagen
styles.css                         algemene UI-styling
data/capacity-scale.js             één gedeelde MW→diameter schaal
data/injections.js                 grote centrales en afgeleide unitproductie
data/province-flow.js              provinciale vraagmodellering en hernieuwbare balans
data/province-demand-model.json    CBS-basisgewichten, profielklassen en aannames
data/interconnectors.js            fysieke grensverbindingen en capaciteit
data/interconnector-flags.js       vlaggen, flowstatus en grensdetails
data/solar-storage.js              solar-LOD, wind op land en batterij-rendering
data/solar-parks.json              volledige gerealiseerde ROM3D-zonneparkset
data/onshore-wind-rivm.json        gegenereerde RIVM-turbines en ≥25 MW clusters
data/solar-storage.json            handmatig geverifieerde batterijopslag
scripts/update_live.py             actuele publieke systeemdata
scripts/fetch_rivm_wind.py         RIVM-wind ingest en clustering
scripts/update_solar_parks.py      ROM3D ArcGIS solar ingest en aggregatie
scripts/check_repo.py              netwerk-vrije consistentiecheck
tests/                             unit tests
```

## Ontwerpregels

1. Geen placeholder-MW of fictieve live data.
2. `measured`, `derived`, `modelled` en `static` worden niet door elkaar gehaald.
3. Geïnstalleerd vermogen en actuele productie zijn verschillende grootheden.
4. Landelijke assetsets gebruiken waar mogelijk een landelijke bron in plaats van een handmatige shortlist.
5. Grote objectsets krijgen LOD; duizenden Leaflet/DOM-objecten worden niet continu gerenderd.
6. Capaciteitssymbolen delen één visuele schaal.
7. Een ingest-workflow mag niet groen eindigen met een lege of evident onwaarschijnlijke dataset.
8. Een provinciale vraagwaarde moet als model zichtbaar blijven en de som van provincies moet exact aan de actuele landelijke vraag worden genormaliseerd.
9. Een getekende provinciale route mag nooit worden gepresenteerd als gemeten fysieke interprovinciale flow.
