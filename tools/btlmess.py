"""전투 연출 파일 chara/btleff2.chr 안에 박힌 이벤트 대사(btl_mess.txt, @100 ~ @999).

리자스 마을 폴크·마르크 전투에서 나오는 "＊「이…이놈들!" 대사. bin/def_motinfo*.pak 안에도 같은 파일이 있다.
제자리 교체: 원래 바이트 수 이하로 쓰고 남는 자리는 반각 공백(게임이 건너뜀)으로 채운다.
번역은 같은 문장인 이벤트 e200/e201/e201_b 의 100번을 쓴다.
"""
import os, re
import dq8arc
from formats import Pak
from extract import read_tsv

BS = chr(92)
CHR = 'chara' + BS + 'btleff2.chr'
PAKS = ['bin' + BS + 'def_motinfo.pak', 'bin' + BS + 'def_motinfo2.pak', 'bin' + BS + 'def_motinfo_2.pak']
PAT = re.compile(rb'(@0\r\n\r\n@100\r\n)(.*?)(\r\n@999\r\n)', re.S)


def text():
    tr = dict(read_tsv(os.path.join(dq8arc.ROOT, 'translation', 'ko', 'event', 'e200', 'e201', 'e201_b.tsv')))
    return tr['100']


def _patch(d, enc):
    m = PAT.search(d)
    assert m, 'btl_mess 없음'
    b = enc(text()).replace(b'\n', b'\r\n')
    n = len(m.group(2))
    assert len(b) <= n, ('btl_mess 길이 초과', len(b), n)
    return d[:m.start(2)] + b + b' ' * (n - len(b)) + d[m.end(2):]


def build(a, files, enc):
    """files 에 이미 있는 것은 그 위에 고친다"""
    out = {CHR: _patch(files.get(CHR) or a.read(a.hd6.get(CHR)), enc)}
    for p in PAKS:
        pk = Pak(files.get(p) or a.read(a.hd6.get(p)))
        pk.put('btleff2.chr', _patch(pk.get('btleff2.chr'), enc))
        out[p] = pk.build()
    return out
