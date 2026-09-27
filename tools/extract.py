"""Dump original Japanese text for translation reference.

translation/jp/event/<path>.tsv   event .txt      id<TAB>text   (\\n = new line)
translation/jp/mes/<file>.tsv     .mes messages  id<TAB>text   ({xxxx} = control code, \\n = 0xff00)
translation/jp/str/<file>.tsv     .str strings   id<TAB>text
translation/mes_fonts.tsv         archive<TAB>pak member<TAB>font (l3 / s3 / skip)
"""
import os, sys, struct
import dq8arc
from formats import Pak, Mes, str_parse, evtxt_parse
from charset import FontTable

ROOT = dq8arc.ROOT
TR = os.path.join(ROOT, 'translation')
BS = '\\'
COMMON = set('のにはをがでとてしたいるうかなもよ。、　！？ーっんすれ')


def esc(s):
    return s.replace('\\', '\\\\').replace('\t', '\\t').replace('\r\n', '\\n').replace('\n', '\\n')


def unesc(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            out.append({'n': '\n', 't': '\t', '\\': '\\'}[s[i + 1]])
            i += 2
        else:
            out.append(s[i])
            i += 1
    return ''.join(out)


def mes_to_text(codes, chars):
    out = []
    for c in codes:
        if c == 0xff00:
            out.append('\n')
        elif c < len(chars):
            out.append(chars[c])
        else:
            out.append('{%04x}' % c)
    return ''.join(out)


def file_key(name, member=''):
    k = name.replace(BS, '/')
    return k + ('__' + member if member else '')


def write_tsv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        for k, v in rows:
            f.write('%s\t%s\n' % (k, esc(v)))


def read_tsv(path):
    rows = []
    if not os.path.exists(path):
        return rows
    for ln in open(path, encoding='utf-8'):
        ln = ln.rstrip('\n')
        if not ln or ln.startswith('#'):
            continue
        k, _, v = ln.partition('\t')
        rows.append((k, unesc(v)))
    return rows


def is_mes(b):
    if len(b) < 8:
        return False
    cnt, _ = struct.unpack_from('<HH', b)
    if cnt == 0 or 4 + 4 * cnt > len(b):
        return False
    prev = -1
    for i in range(cnt):
        _, off = struct.unpack_from('<HH', b, 4 + 4 * i)
        p = 2 * (off + cnt + 1)
        if off < prev or p < 4 + 4 * cnt - 2 or p > len(b):
            return False
        prev = off
    for i in range(min(cnt, 20)):
        _, off = struct.unpack_from('<HH', b, 4 + 4 * i)
        p = 2 * (off + cnt + 1)
        if b'\x01\xff' not in b[p:p + 4000] and p < len(b) - 4:
            return False
    return b'\x01\xff' in b


# item / spell name lists have few particles, so the heuristic cannot tell them apart
FORCE = {'meswin' + BS + 'system_l.mes': 'l3', 'meswin' + BS + 'system_s.mes': 's3'}

SKIP_EXT = ('.chr', '.img', '.tm2', '.mds', '.wav', '.snd', '.map', '.mpk', '.ipk', '.sky', '.tm2pak', '.pss')


def find_mes(a):
    out = []
    for e in a.hd6.entries:
        n = e.name.lower()
        if e.size > 3_000_000 or n.endswith(SKIP_EXT) or n.startswith('dbg' + BS):
            continue
        b = a.read(e)
        if is_mes(b):
            out.append((e.name, '', b))
        if n.endswith(('.pak', '.pac')):
            try:
                pk = Pak(b)
                for m in pk.names():
                    d = pk.get(m)
                    if m.endswith(('.mes', '.bin')) and is_mes(d):
                        out.append((e.name, m, d))
            except Exception:
                pass
    return out


def main():
    a = dq8arc.arc()
    L = FontTable(a.read('meswin' + BS + 'fonttbl_l3.bin')).chars()
    S = FontTable(a.read('meswin' + BS + 'fonttbl_s3.bin')).chars()

    # event txt
    n_ev = 0
    for e in a.hd6.entries:
        if e.name.startswith('event' + BS + 'e') and e.name.endswith('.txt'):
            rows = [(h, b.decode('cp932')) for h, b in evtxt_parse(a.read(e)) if h != '9999999']
            write_tsv(os.path.join(TR, 'jp', 'event', file_key(e.name)[len('event/'):-4] + '.tsv'), rows)
            n_ev += 1

    # mes
    reg = []
    for name, member, b in find_mes(a):
        msgs = Mes(b).messages()
        sl = sr = 0
        n = 0
        for _, w in msgs:
            for c in w:
                if c < 0xf000:
                    n += 1
                    sl += c < len(L) and L[c] in COMMON
                    sr += c < len(S) and S[c] in COMMON
        font = 'l3' if sl >= sr else 's3'
        if max(sl, sr) < 0.35 * max(n, 1) or (name.startswith('event' + BS + 'talk_mes')):
            font = 'skip'          # stale files encoded with an older table
        font = FORCE.get(name, font)
        reg.append((name, member, font))
        if font != 'skip':
            T = L if font == 'l3' else S
            write_tsv(os.path.join(TR, 'jp', 'mes', file_key(name, member) + '.tsv'),
                      [(str(mid), mes_to_text(w, T)) for mid, w in msgs])
    with open(os.path.join(TR, 'mes_fonts.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        for r in reg:
            f.write('\t'.join(r) + '\n')

    # str in menu/cmd4.pac
    pk = Pak(a.read('menu' + BS + 'cmd4.pac'))
    write_tsv(os.path.join(TR, 'jp', 'str', 'menu/cmd4.pac__cmdstr.str.tsv'),
              [(str(mid), s.decode('cp932')) for mid, s in str_parse(pk.get('cmdstr.str'))])
    print('event txt', n_ev, 'mes', len(reg), 'skip', sum(r[2] == 'skip' for r in reg))


if __name__ == '__main__':
    main()
