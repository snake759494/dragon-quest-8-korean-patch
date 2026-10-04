"""맵 스크립트(map\\**\\*.stb, title\\title.stb 등) 안의 SJIS 대사 문자열.

stb 안에는 모션 이름 같은 라벨(立ち, 本調べる …)도 SJIS로 있다. 라벨은 이름으로 참조되므로 건드리지 않고,
문장부호(。！？…「」)·줄바꿈이 있거나 ○強主○ 토큰이 있는 '문장'만 대상으로 한다.
같은 문장이 여러 파일에 반복되므로 번역은 고유 문장 단위(translation/jp/stb/stb.tsv, 키 = 해시).
적용: 원래 바이트 길이 이하로 제자리 교체, 남는 자리는 NUL.
"""
import os, re, hashlib
import dq8arc
from extract import write_tsv, read_tsv

ROOT = dq8arc.ROOT
TR = os.path.join(ROOT, 'translation')
SJ = re.compile(rb'(?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]|[\x20-\x7e\xa1-\xdf\n])+\x00')   # \xa1-\xdf: 반각 ｢｣ 등
SENT = re.compile(r'[。！？…「」、]|\n|○強主○')
JP = re.compile(r'[぀-ヿ一-鿿]')
SIGN = re.compile(r'^(この先|これより)[^　]*　|　→$')            # 표지판 (문장부호 없음)


def is_stb(name):
    n = name.lower()
    return n.endswith('.stb') and (n.startswith('map\\') or n.startswith('title\\'))


def key(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()[:10]


def sentences(data):
    out = []
    for m in SJ.finditer(data):
        if m.start() and data[m.start() - 1] != 0:
            continue
        raw = m.group()[:-1]
        try:
            s = raw.decode('cp932')
        except UnicodeDecodeError:
            continue
        if JP.search(s) and (SENT.search(s) or SIGN.search(s)):
            out.append((m.start(), len(raw), s))
    return out


def dump():
    a = dq8arc.arc()
    uniq, count = {}, {}
    for e in a.hd6.entries:
        if is_stb(e.name):
            for off, n, s in sentences(a.read(e)):
                k = key(s)
                uniq.setdefault(k, s)
                count[k] = count.get(k, 0) + 1
    rows = sorted(uniq.items(), key=lambda kv: -count[kv[0]])
    write_tsv(os.path.join(TR, 'jp', 'stb', 'stb.tsv'), rows)
    print('stb 고유 문장', len(rows), '글자', sum(len(s) for _, s in rows))


def build(enc):
    """번역된 문장을 모든 stb에 적용 -> {name: bytes}"""
    tr = {}
    for f in os.listdir(os.path.join(TR, 'ko', 'stb')) if os.path.isdir(os.path.join(TR, 'ko', 'stb')) else []:
        tr.update(read_tsv(os.path.join(TR, 'ko', 'stb', f)))
    if not tr:
        return {}
    a = dq8arc.arc()
    files = {}
    for e in a.hd6.entries:
        if not is_stb(e.name):
            continue
        d = bytearray(a.read(e))
        hit = False
        for off, n, s in sentences(d):
            k = key(s)
            if k in tr:
                b = enc(tr[k])
                if len(b) > n:
                    raise ValueError('stb 문장 길이 초과 %s: %d > %d' % (k, len(b), n))
                d[off:off + n] = b + b'\0' * (n - len(b))
                hit = True
        if hit:
            files[e.name] = bytes(d)
    return files


if __name__ == '__main__':
    dump()
