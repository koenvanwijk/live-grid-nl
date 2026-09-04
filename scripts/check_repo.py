#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
def main():
    solar=load('data/solar-parks.json');parks=solar.get('parks') or [];assert solar.get('schema_version')==3;assert solar.get('overview_threshold_mwp')==25.0;assert len(parks)==solar.get('stats',{}).get('physical_parks');assert len(parks)>=100;assert any(0<float(p.get('capacity_mwp',0))<25 for p in parks);overview=[p for p in parks if float(p.get('capacity_mwp',0))>=25];assert len(overview)==solar.get('stats',{}).get('overview_ge25mwp');assert all(p.get('status')=='operationeel' for p in parks);assert all(float(p.get('capacity_mwp',0))>0 for p in parks)
    solar_js=(ROOT/'data/solar-storage.js').read_text(encoding='utf-8');[(_ for _ in ()).throw(AssertionError(x)) if x not in solar_js else None for x in ('solarThreshold','z<8?25','z<9.5?10','z<11?5','z<12.5?2','MAX_VISIBLE_SOLAR','solarToggle','onshoreWindToggle','storageToggle')]
    wind=load('data/onshore-wind-rivm.json');assert wind.get('source',{}).get('provider')=='RIVM';assert len(wind.get('turbines') or [])>1000;assert len(wind.get('clusters') or [])>10
    storage=load('data/solar-storage.json');assert 'solar' not in storage;assert storage.get('thresholds')=={'storage_mw':25}
    demand=load('data/province-demand-model.json');assert len(demand.get('provinces') or {})==12;assert demand.get('population_source',{}).get('provider')=='CBS';assert len(demand.get('assumptions') or [])>=5
    province_flow=(ROOT/'data/province-flow.js').read_text(encoding='utf-8')
    for fragment in ('generation_by_province','wind_onshore_mw','solar_mw','province-demand-model.json','demandByProvince','EDGES','routeRedistribution','Gemodelleerde provinciale hernieuwbare flow','movingDot'):assert fragment in province_flow,fragment
    assert 'gemeten fysieke' in province_flow.lower()

    collector=(ROOT/'scripts/update_live.py').read_text(encoding='utf-8')
    for fragment in ("documentType':'A65'","documentType':'A75'","documentType':'A11'",'latest_common_timestamp','aligned_entso_balance','CORE_BORDERS',"national_balance_source']='ENTSO-E aligned'",'balance_timestamp','in_Domain receives'):assert fragment in collector,fragment
    overlay=(ROOT/'scripts/overlay_ned_generation_mix.py').read_text(encoding='utf-8')
    for fragment in ('ENTSO-E aligned','ned_load_mw','ned_generation_mw','apply_ned_fallback','ned_generation_mix','set_ned_comparison'):assert fragment in overlay,fragment
    provenance=(ROOT/'scripts/enrich_provenance.py').read_text(encoding='utf-8');assert "national_balance_source')=='ENTSO-E aligned'" in provenance;assert "source='ENTSO-E'" in provenance
    freshness=(ROOT/'data/headline-freshness.js').read_text(encoding='utf-8')
    for fragment in ('balance_timestamp','ENTSO-E systeembalans','NED controle vraag','NED controle opwek','balans sluit nog niet'):assert fragment in freshness,fragment
    index=(ROOT/'index.html').read_text(encoding='utf-8');assert 'data/headline-freshness.js' in index;assert 'data/layer-toggle-colors.css' in index
    for path in ['data/capacity-scale.js','data/injections.js','data/solar-storage.js','data/interconnector-flags.js','data/capacity-overrides.js']:assert 'capacityDiameter' in (ROOT/path).read_text(encoding='utf-8'),path
    print('repository consistency: OK')
if __name__=='__main__':main()
