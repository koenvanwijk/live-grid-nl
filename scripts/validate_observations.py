#!/usr/bin/env python3
import json
from pathlib import Path

ALLOWED_PROVENANCE={'measured','derived','modelled','static'}
ALLOWED_TEMPORAL={'actual','forecast','none'}

def walk(node,path='observations'):
    if isinstance(node,dict):
        if 'provenance' in node and 'temporal' in node:
            p=node['provenance']; t=node['temporal']
            assert p in ALLOWED_PROVENANCE, f'{path}: invalid provenance {p}'
            assert t in ALLOWED_TEMPORAL, f'{path}: invalid temporal {t}'
            if p=='static': assert t=='none', f'{path}: static must use temporal=none'
            if t=='forecast': assert p!='measured', f'{path}: forecast may not be labelled measured'
            if p in {'measured','derived','modelled'}: assert node.get('source'), f'{path}: source required'
        for k,v in node.items(): walk(v,f'{path}.{k}')
    elif isinstance(node,list):
        for i,v in enumerate(node): walk(v,f'{path}[{i}]')

data=json.loads(Path('data/live.json').read_text())
assert data.get('schema_version')==2
assert isinstance(data.get('observations'),dict)
walk(data['observations'])
print('observation model valid')
