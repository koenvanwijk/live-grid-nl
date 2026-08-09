# NL Live Grid

Interactieve kaart van het Nederlandse hoogspanningsnet, geïnspireerd op de live grid-weergave van Energinet.

## Wat werkt nu

- Officiële openbare **TenneT TSO B.V.** assetdata wordt rechtstreeks in de browser geladen.
- Bovengrondse lijnen, ondergrondse kabels en hoogspanningsstations vanaf 110 kV.
- Filters voor 110 / 150 / 220 / 380 kV.
- Responsive dashboard voor desktop en mobiel.
- Geen verzonnen MW-waarden: interne vermogensstromen worden pas getoond zodra het state-estimation model beschikbaar is.

## Databron

TenneT Assets Hoogspanning ArcGIS FeatureServer:

`https://services-eu1.arcgis.com/WjozPuR5ROn6NZE8/ArcGIS/rest/services/TenneT_Assets_Hoogspanning/FeatureServer`

Gebruikte lagen:

- 2 — Hoogspanning leiding (bovengronds)
- 3 — Hoogspanning kabel (ondergronds)
- 5 — Hoogspanning station

De dataset bevat openbare Nederlandse TenneT-assets van 110 kV en hoger en wordt door TenneT periodiek bijgewerkt.

## Volgende stap: echte live grid state

Doelarchitectuur:

1. TenneT asset topology normaliseren naar een elektrisch bus/branch-model.
2. Live nationale en regionale injecties ophalen uit TenneT/NED.
3. Grensstromen uit TenneT/ENTSO-E toevoegen.
4. Netwerktopologie verrijken met elektrische parameters.
5. DC power flow / state estimation uitvoeren.
6. Per verbinding richting, MW, benuttingsgraad en confidence tonen.
7. Gemeten, afgeleide en gemodelleerde waarden in de UI expliciet onderscheiden.

## Lokaal draaien

Omdat de kaart externe API's gebruikt is een simpele HTTP-server aanbevolen:

```bash
python3 -m http.server 8080
```

Open daarna `http://localhost:8080`.
