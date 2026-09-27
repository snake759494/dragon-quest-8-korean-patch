"""맵(지역) 이름: map\\map10.cfg (M "id","이름","표시 이름",...) 와 map\\map.cfg (MAP_NAME "id","이름",...).
따옴표 문자열 중 일본어가 든 것을 번역표(translation/ko/map/mapnames.tsv: 일본어 <TAB> 한국어)로 바꾼다.
지도 화면의 마을 이름 등이 여기서 나온다.
"""
import os
import dq8arc, btltext
from extract import read_tsv

ROOT = dq8arc.ROOT
FILES = ['map/map10.cfg', 'map/map.cfg', 'map/map7.cfg', 'map/map8.cfg', 'map/map9.cfg']
TSV = os.path.join(ROOT, 'translation', 'ko', 'map', 'mapnames.tsv')


def table():
    return dict(read_tsv(TSV)) if os.path.exists(TSV) else {}


def texts():
    return list(table().values())


def build(a, enc):
    t = table()
    out = {}
    for n in FILES:
        d = a.read(a.hd6.get(n))
        tr = {k: t[s] for k, s in btltext.quoted_items(d) if s in t}
        out[n] = btltext.quoted_apply(d, tr, enc)
    return out
