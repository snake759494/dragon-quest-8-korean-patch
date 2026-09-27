"""bin\\bin_ext.pak 안의 전투·아이템 텍스트.

QUOTED: 스크립트형 SJIS 텍스트(ACT_MES_TEXT id,"..."; / NAME n,"..."; 등). 키 = 줄 번호(0부터).
         한 줄에 따옴표 문자열이 여러 개면 키 = 줄번호.k
RECORDS: 고정 길이 레코드 안의 이름 칸 (파일, 첫 레코드 위치, 레코드 크기, 이름 위치, 이름 칸 크기)
"""
import os, re
import dq8arc
from formats import Pak
from extract import write_tsv, read_tsv

ROOT = dq8arc.ROOT
TR = os.path.join(ROOT, 'translation')
PAK = 'bin\\bin_ext.pak'

QUOTED = ['actmsg_text_2.txt', 'acteffmsg_text_1.txt', 'actextmsg_text_1.txt', 'itemstr1.lst']
RECORDS = {
    'btl_monster_param_9.bin': (0x40, 0x80, 0x10, 0x20),
    'haikai_name_3.bin': (0x20, 0x10, 0x06, 0x0a),
}
JP = re.compile(r'[぀-ヿ一-鿿]')
Q = re.compile(rb'"((?:[\x81-\x9f\xe0-\xfc][\x40-\xfc]|[^"\x81-\x9f\xe0-\xfc])*)"')


def quoted_items(data):
    lines = data.split(b'\n')
    out = []
    for i, ln in enumerate(lines):
        ms = list(Q.finditer(ln))
        for k, m in enumerate(ms):
            s = m.group(1).decode('cp932')
            if JP.search(s):
                out.append(('%d' % i if len(ms) == 1 else '%d.%d' % (i, k), s))
    return out


def quoted_apply(data, tr, enc):
    lines = data.split(b'\n')
    for i, ln in enumerate(lines):
        ms = list(Q.finditer(ln))
        if not ms:
            continue
        parts, pos = [], 0
        for k, m in enumerate(ms):
            key = '%d' % i if len(ms) == 1 else '%d.%d' % (i, k)
            parts.append(ln[pos:m.start(1)])
            parts.append(enc(tr[key]) if key in tr else m.group(1))
            pos = m.end(1)
        parts.append(ln[pos:])
        lines[i] = b''.join(parts)
    return b'\n'.join(lines)


def record_items(data, spec):
    first, size, at, n = spec
    out = []
    for o in range(first, len(data) - size + 1, size):
        raw = data[o + at:o + at + n].split(b'\0')[0]
        try:
            s = raw.decode('cp932')
        except UnicodeDecodeError:
            continue
        if JP.search(s):
            out.append(('%x' % o, s))
    return out


def record_apply(data, spec, tr, enc):
    first, size, at, n = spec
    d = bytearray(data)
    for key, s in tr.items():
        o = int(key, 16)
        b = enc(s)
        assert len(b) < n, ('name too long', key, s)
        d[o + at:o + at + n] = b + b'\0' * (n - len(b))
    return bytes(d)


def dump():
    pk = Pak(dq8arc.read(PAK))
    for nm in QUOTED:
        write_tsv(os.path.join(TR, 'jp', 'btl', nm + '.tsv'), quoted_items(pk.get(nm)))
    for nm, spec in RECORDS.items():
        write_tsv(os.path.join(TR, 'jp', 'btl', nm + '.tsv'), record_items(pk.get(nm), spec))


def build(enc):
    """번역을 반영한 bin_ext.pak과 같은 이름의 개별 파일(bin_ext\\*)을 돌려준다"""
    a = dq8arc.arc()
    pk = Pak(a.read(PAK))
    files = {}
    for nm in QUOTED + list(RECORDS):
        tr = dict(read_tsv(os.path.join(TR, 'ko', 'btl', nm + '.tsv')))
        if not tr:
            continue
        d = pk.get(nm)
        d = quoted_apply(d, tr, enc) if nm in QUOTED else record_apply(d, RECORDS[nm], tr, enc)
        pk.put(nm, d)
        single = 'bin_ext\\' + nm
        if single.lower() in a.hd6.by_name:
            files[single] = d
    files[PAK] = pk.build()
    return files


if __name__ == '__main__':
    dump()
