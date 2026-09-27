"""DATA 아카이브 파일 안의 NUL 로 끝나는 SJIS 문자열을 제자리 교체 (elfstr 와 같은 방식, 길이는 원래 이하).

FILES: {아카이브 이름: pak 안 멤버 이름(없으면 None)} — 같은 내용이 bin_ext.pak 안과 개별 파일 양쪽에 있으면 둘 다 고친다.
번역: translation/ko/inplace/<이름>.tsv  (키 = 16진수 오프셋)
"""
import os
import dq8arc, elfstr
from extract import esc, read_tsv

ROOT = dq8arc.ROOT
TR = os.path.join(ROOT, 'translation')
TRODE_MES = (0x2C900, 0x3A702)          # senreki2.chr 안 트로데 코멘트 mes (570개)
FILES = ['menu/senreki2.chr', 'bin_ext/rkh.lst', 'bin_ext/slay_monster_list_2.bin']
# 문자열이 아니라 구조 안에 박힌 글자 코드 (파일, 오프셋, 원래 글자, 바꿀 글자)
CODES = [('menu/senreki2.chr', 0x2C2F4, '個', '개')]   # 도감·기록의 개수 단위
PAK_MEMBERS = {'bin_ext/rkh.lst': ('bin/bin_ext.pak', 'rkh.lst')}


def key(name):
    return name.replace('/', '_')


def dump():
    a = dq8arc.arc()
    d = os.path.join(TR, 'jp', 'inplace')
    os.makedirs(d, exist_ok=True)
    for n in FILES:
        ss = elfstr.find_strings(a.read(a.hd6.get(n)))
        with open(os.path.join(d, key(n) + '.tsv'), 'w', encoding='utf-8', newline='\n') as o:
            for off, ln, t in ss:
                o.write('%06x\t%s\n' % (off, esc(t)))
        print(n, len(ss))


def load():
    out = {}
    for n in FILES:
        p = os.path.join(TR, 'ko', 'inplace', key(n) + '.tsv')
        out[n] = dict(read_tsv(p)) if os.path.exists(p) else {}
    return out


def apply(data, tr, enc, name=None):
    data = bytearray(data)
    for n, off, old, new in CODES:
        if n == name:
            assert data[off:off + 2] == old.encode('cp932'), (n, hex(off))
            data[off:off + 2] = enc(new)
    for k, text in tr.items():
        off = int(k, 16)
        end = data.index(b'\0', off)
        b = enc(text)
        assert len(b) <= end - off, ('문자열 초과', k, text, len(b), end - off)
        data[off:end] = b + b'\0' * (end - off - len(b))
    return bytes(data)


def apply_by_order(data, ref, tr, enc):
    """ref(개별 파일) 의 오프셋 키 번역을, 같은 문자열이 같은 순서로 든 data(pak 안 사본)에 적용"""
    rs = elfstr.find_strings(ref)
    ds = elfstr.find_strings(data)
    assert [t for _, _, t in rs] == [t for _, _, t in ds]
    m = {'%06x' % d[0]: tr[k] for d, (ro, _, _) in zip(ds, rs) for k in ['%06x' % ro] if k in tr}
    return apply(data, m, enc)


if __name__ == '__main__':
    dump()
