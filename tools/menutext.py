"""추가 메뉴·책 텍스트.

BOOKS    : 책장 책 본문 (이벤트 txt 형식, 줄바꿈 LF)          -> translation/{jp,ko}/book/<이름>.tsv
STRS     : id 표 + SJIS 문자열(.str)                          -> translation/{jp,ko}/str/<키>.tsv
MCSTRING : 세이브 화면 문구, 0x30부터 0x60바이트 고정 칸       -> translation/{jp,ko}/str/menu/mcard2.pak__mcstring.str.tsv
MCLIST   : 세이브 화면 장 이름, 0x10부터 0x20바이트(이름 +4)   -> translation/{jp,ko}/str/menu/mcard2.pak__mcstrlist.bin.tsv
"""
import os
import dq8arc
from formats import Pak, str_parse, str_build, evtxt_parse, evtxt_build
from extract import write_tsv, read_tsv, file_key

TR = os.path.join(dq8arc.ROOT, 'translation')
BS = '\\'
LF = bytes([10])
BOOKS = ['event' + BS + 'book' + BS + 'bookmes.txt', 'bin_ext' + BS + 'bookmes.txt']
STRS = [('menu' + BS + 'item_c.pak', 'i_cole.str'), ('menu' + BS + 'mons_c.pak', 'mons_team.str'),
        ('menu' + BS + 'itemrecipe.str', ''), ('menu' + BS + 'sml' + BS + 'sml.str', '')]
MCPAK = 'menu' + BS + 'mcard2.pak'


def _get(n, m):
    d = dq8arc.read(n)
    return Pak(d).get(m) if m else d


def dump():
    for n in BOOKS:
        rows = [(h, b.decode('cp932')) for h, b in evtxt_parse(dq8arc.read(n), LF) if h not in ('9999', '9999999')]
        write_tsv(os.path.join(TR, 'jp', 'book', file_key(n).replace('/', '_') + '.tsv'), rows)
    for n, m in STRS:
        write_tsv(os.path.join(TR, 'jp', 'str', file_key(n, m) + '.tsv'),
                  [(str(i), s.decode('cp932')) for i, s in str_parse(_get(n, m))])
    pk = Pak(dq8arc.read(MCPAK))
    d = pk.get('mcstring.str')
    write_tsv(os.path.join(TR, 'jp', 'str', file_key(MCPAK, 'mcstring.str') + '.tsv'),
              [('%x' % o, d[o:o + 0x60].split(b'\0')[0].decode('cp932')) for o in range(0x30, len(d), 0x60)])
    d = pk.get('mcstrlist.bin')
    write_tsv(os.path.join(TR, 'jp', 'str', file_key(MCPAK, 'mcstrlist.bin') + '.tsv'),
              [('%x' % o, d[o + 4:o + 0x20].split(b'\0')[0].decode('cp932')) for o in range(0x10, len(d), 0x20)])


def ko(path):
    return dict(read_tsv(os.path.join(TR, 'ko', path)))


def texts():
    """번역문 전체(글자 수집용): (메뉴 폰트 우선 텍스트, 대사 폰트 텍스트)"""
    menu, dia = [], []
    for n, m in STRS:
        menu += list(ko(os.path.join('str', file_key(n, m) + '.tsv')).values())
    for m in ('mcstring.str', 'mcstrlist.bin'):
        menu += list(ko(os.path.join('str', file_key(MCPAK, m) + '.tsv')).values())
    for n in BOOKS:
        dia += list(ko(os.path.join('book', file_key(n).replace('/', '_') + '.tsv')).values())
    return menu, dia


def build(to_sjis):
    files = {}
    for n in BOOKS:
        tr = ko(os.path.join('book', file_key(n).replace('/', '_') + '.tsv'))
        if tr:
            bl = [(h, to_sjis(tr[h]).replace(bytes([10]), LF) if h in tr else b) for h, b in evtxt_parse(dq8arc.read(n), LF)]
            files[n] = evtxt_build(bl, LF)
    paks = {}
    for n, m in STRS:
        tr = ko(os.path.join('str', file_key(n, m) + '.tsv'))
        if not tr:
            continue
        d = str_build([(i, to_sjis(tr[str(i)]) if str(i) in tr else s) for i, s in str_parse(_get(n, m))])
        if m:
            paks.setdefault(n, Pak(dq8arc.read(n))).put(m, d)
        else:
            files[n] = d
    pk = paks.setdefault(MCPAK, Pak(dq8arc.read(MCPAK)))
    for m, first, size, at in (('mcstring.str', 0x30, 0x60, 0), ('mcstrlist.bin', 0x10, 0x20, 4)):
        tr = ko(os.path.join('str', file_key(MCPAK, m) + '.tsv'))
        d = bytearray(pk.get(m))
        for key, text in tr.items():
            o = int(key, 16) + at
            n = size - at
            b = to_sjis(text)
            assert len(b) < n, ('길이 초과', m, key, text)
            d[o:o + n] = b + b'\0' * (n - len(b))
        pk.put(m, bytes(d))
    for n, p in paks.items():
        files[n] = p.build()
    return files


if __name__ == '__main__':
    dump()
