"""한글 ISO 빌드: 번역(translation/ko) -> 폰트표·폰트 텍스처·mes·이벤트 txt·str -> ISO.

python tools/build.py [출력 ISO]
"""
import os, sys, re, collections
import instr, itemana, mapname, dq8arc, isopatch, btltext, namepad, stbtext, menutext, title_logo
VOICE_MODE = os.environ.get('DQ8_VOICE', '')      # '' | 'test' | 'full'
from font16 import patch_font16
from elfstr import read_iso_file
from formats import Pak, Mes, str_parse, str_build, evtxt_parse, evtxt_build
from charset import FontTable, korean_table, char_code, is_hangul, charmap
from fonttex import FontPak, render, CAPACITY, CH
SPACE_W = 7   # 반각 공백 폭(px)
SPACE = 0x5F  # 0x20은 게임이 폭 0으로 처리 -> 번역문 공백은 '_' 코드에 빈 글리프로 넣음
from extract import read_tsv, file_key

ROOT = dq8arc.ROOT
TR = os.path.join(ROOT, 'translation')
BS = '\\'
OUT_ISO = os.path.join(ROOT, 'DQ8_KR.iso')
ELF_FILES = ['SLPM_658.88', 'BIN/MENU.BIN', 'BIN/CASINO.BIN']
FALLBACK = 0x81A1
# 표에 없는 문자 -> 비슷한 표 안 문자
SUBST = {"'": '’', '"': '”', '·': '・', '‘': '’', '“': '”', '—': '―', '–': '-', '♥': '♪', '｢': '「', '｣': '」'}
MISSING = {}      # ■ : 표에 없는 일본어 글자 대체
TOKEN = re.compile(r'\{([0-9a-f]{4})\}')


def ko_rows(kind, key):
    base = os.path.join(TR, 'ko', kind, key)
    rows = dict(read_tsv(base + '.tsv'))
    for k in range(1, 10):                      # 나눠서 번역한 파일 (key.part1.tsv ...)
        rows.update(read_tsv('%s.part%d.tsv' % (base, k)))
    return rows


def hangul_of(texts):
    c = collections.Counter()
    for t in texts:
        c.update(ch for ch in TOKEN.sub('', t) if is_hangul(ch))
    return c


def main(out_iso=OUT_ISO):
    a = dq8arc.arc()
    Lj = FontTable(a.read('meswin' + BS + 'fonttbl_l3.bin'))
    Sj = FontTable(a.read('meswin' + BS + 'fonttbl_s3.bin'))
    reg = [ln.rstrip('\n').split('\t') for ln in open(os.path.join(TR, 'mes_fonts.tsv'), encoding='utf-8')]

    # ---- 번역 읽기
    ev = {}
    for e in a.hd6.entries:
        if e.name.startswith('event' + BS + 'e') and e.name.endswith('.txt'):
            ev[e.name] = ko_rows('event', file_key(e.name)[len('event/'):-4])
    mes = {(n, m): ko_rows('mes', file_key(n, m)) for n, m, f in reg if f != 'skip'}
    STR_KEY = ('menu' + BS + 'cmd4.pac', 'cmdstr.str')
    strs = ko_rows('str', file_key(*STR_KEY))

    # ---- 글자 수집
    l3_texts = [t for d in ev.values() for t in d.values()] + list(strs.values())
    s3_texts = list(strs.values())
    for (n, m), d in mes.items():
        f = dict(((x, y), z) for x, y, z in reg)[(n, m)]
        (l3_texts if f == 'l3' else s3_texts).extend(d.values())
    # 전투 텍스트(대사창) / 몬스터 이름·이름 입력판(대사·메뉴 양쪽)
    btl = {nm: dict(read_tsv(os.path.join(TR, 'ko', 'btl', nm + '.tsv'))) for nm in btltext.QUOTED + list(btltext.RECORDS)}
    elf_tr = {f: dict(read_tsv(os.path.join(TR, 'ko', 'elf', f.replace('/', '_') + '.tsv'))) for f in ELF_FILES}
    both = [t for nm in btltext.RECORDS for t in btl[nm].values()] + [''.join(namepad.ALL)]
    l3_texts += [t for nm in btltext.QUOTED for t in btl[nm].values()] + both
    inpl = instr.load()                             # 전투 기록 화면·연금 레시피 힌트 (제자리 교체)
    both += [t for d in elf_tr.values() for t in d.values()]   # 실행 파일 문자열: 메뉴(s3)·대사(l3) 양쪽에 쓰임
    both += [t for d in inpl.values() for t in d.values()]
    both += itemana.texts()                         # 아이템 분석(분류·능력치·설명)
    both += mapname.texts()                         # 맵(지역) 이름
    l3_texts += both
    s3_texts += both + list(btl['itemstr1.lst'].values())       # 아이템 이름·설명은 메뉴 글자로 우선
    mt_menu, mt_dia = menutext.texts()
    s3_texts += mt_menu
    l3_texts += mt_menu + mt_dia
    stb_tr = {}
    if os.path.isdir(os.path.join(TR, 'ko', 'stb')):
        for f in os.listdir(os.path.join(TR, 'ko', 'stb')):
            stb_tr.update(read_tsv(os.path.join(TR, 'ko', 'stb', f)))
    l3_texts += list(stb_tr.values())
    hl = hangul_of(l3_texts)
    hs = hangul_of(s3_texts)
    for ch in list(hl) + list(hs):
        charmap()[ch]                           # KS X 1001 밖 글자 검사
    Lk, dl = korean_table(Lj, hl, CAPACITY['l3'])
    # s3: 메뉴 글자 우선, 남는 자리에 대사 글자(빈도순)
    room = min(2044, CAPACITY['s3']) - Sj.n_nonkanji
    extra = [ch for ch, _ in (hl - hs).most_common() if ch not in hs]
    Sk, ds = korean_table(Sj, list(hs) + extra[:max(0, room - len(hs))], CAPACITY['s3'])
    print('l3 표 %d자 (한글 %d)  s3 표 %d자 (한글 %d)' % (len(Lk.codes), len(Lk.codes) - Lk.n_nonkanji,
                                                    len(Sk.codes), len(Sk.codes) - Sk.n_nonkanji))

    files = {}
    files['meswin' + BS + 'fonttbl_l3.bin'] = Lk.build()
    files['meswin' + BS + 'fonttbl_s3.bin'] = Sk.build()

    # ---- 폰트 텍스처
    raw = a.read('meswin' + BS + 'font_tex_l3s3.pak')
    src, dst = FontPak(raw), FontPak(raw)
    for font, J, K in (('l3', Lj, Lk), ('s3', Sj, Sk)):
        for i, c in enumerate(K.codes):
            if c == SPACE:
                # 0x20은 게임이 건너뜀 -> 번역문 공백은 빈 "_" 글리프(반각)로
                g = src.get(font, J.index[c]) * 0
                pass                         # ASCII 영역 글자는 항상 반각(9px) 폭 -> 완전히 빈 글리프
                dst.put(font, i, g)
            elif c < 0x889f and c in J.index:
                dst.put(font, i, src.get(font, J.index[c]))
            else:
                ch = [h for h, v in charmap().items() if v == c][0]
                dst.put(font, i, render(ch, font))
    files['meswin' + BS + 'font_tex_l3s3.pak'] = dst.build()

    # ---- 인코딩 도우미
    def enc_ko(text, T):
        out, i = [], 0
        while i < len(text):
            m = TOKEN.match(text, i)
            if m:
                out.append(int(m.group(1), 16)); i = m.end(); continue
            ch = text[i]; i += 1
            if ch == '\n':
                out.append(0xff00)
            else:
                c = char_code('_' if ch == ' ' else SUBST.get(ch, ch))
                if c not in T.index and c < 0x80:          # 표에 없는 ASCII(~ 등)는 전각으로
                    try:
                        c = char_code(chr(c + 0xfee0))
                    except (UnicodeEncodeError, AssertionError):
                        pass
                if c not in T.index:
                    MISSING[ch] = MISSING.get(ch, 0) + 1
                    c = FALLBACK
                out.append(T.index[c])
        return out

    def reenc_jp(codes, J, T):
        fb = T.index[FALLBACK]
        out = []
        for c in codes:
            if c >= 0xf000 or c >= len(J.codes):
                out.append(c)
            else:
                sj = J.codes[c]
                out.append(T.index[sj] if sj < 0x889f and sj in T.index else fb)
        return out

    # ---- mes
    paks = {}
    for n, m, f in reg:
        if f == 'skip':
            continue
        J, T = (Lj, Lk) if f == 'l3' else (Sj, Sk)
        b = a.read(n) if not m else None
        if m:
            paks.setdefault(n, Pak(a.read(n)))
            b = paks[n].get(m)
        ms = Mes(b)
        tr = mes[(n, m)]
        for mid, w in ms.messages():
            ms.set(mid, enc_ko(tr[str(mid)], T) if str(mid) in tr else reenc_jp(w, J, T))
        if m:
            paks[n].put(m, ms.build())
        else:
            files[n] = ms.build()

    # ---- str (SJIS, 실행 중 변환)
    def sanitize(bs, T):
        out, i = bytearray(), 0
        while i < len(bs):
            c = bs[i]
            if 0x81 <= c <= 0x9f or 0xe0 <= c <= 0xfc:
                code = c << 8 | bs[i + 1]
                if code >= 0x889f or code not in T.index:
                    code = FALLBACK
                out += bytes([code >> 8, code & 0xff]); i += 2
            else:
                out.append(c); i += 1
        return bytes(out)

    def to_sjis(text):
        out = bytearray()
        for ch in text:
            c = char_code('_' if ch == ' ' else SUBST.get(ch, ch))
            if c not in Lk.index and c < 0x80 and ch == '~':
                c = char_code('～')
            out += bytes([c]) if c < 0x100 else bytes([c >> 8, c & 0xff])
        return bytes(out)

    pk = paks.setdefault(STR_KEY[0], Pak(a.read(STR_KEY[0])))
    items = [(mid, to_sjis(strs[str(mid)]) if str(mid) in strs else sanitize(s, Sk))
             for mid, s in str_parse(pk.get(STR_KEY[1]))]
    pk.put(STR_KEY[1], str_build(items))
    for n, p in paks.items():
        files[n] = p.build()

    # ---- 이벤트 txt
    voice_marks, voice_files = {}, []
    if VOICE_MODE:
        import voice
        voice_marks, voice_files = voice.plan(VOICE_MODE)
    for n, tr in ev.items():
        blocks = [(h, to_sjis(tr[h]).replace(b'\n', b'\r\n') if h in tr else sanitize(body, Lk))
                  for h, body in evtxt_parse(a.read(n))]
        if VOICE_MODE:
            stem = os.path.basename(n)[:-4]
            blocks = [(h, voice_marks[(stem, h)] + b if (stem, h) in voice_marks else b) for h, b in blocks]
        files[n] = evtxt_build(blocks)

    # ---- 전투 텍스트·몬스터 이름 (bin\bin_ext.pak + 개별 bin_ext 파일)
    files.update(btltext.build(to_sjis))
    files.update(stbtext.build(to_sjis))
    files.update(menutext.build(to_sjis))
    files.update(title_logo.build())                # 타이틀 로고 부제
    files.update(mapname.build(a, to_sjis))
    files[itemana.NAME] = itemana.build(a.read(a.hd6.get(itemana.NAME)), to_sjis)
    for n, tr in inpl.items():                      # 전투 기록 화면·연금 레시피 힌트
        if not tr:
            continue
        files[n] = instr.apply(a.read(a.hd6.get(n)), tr, to_sjis)
        if n in instr.PAK_MEMBERS:                  # bin_ext.pak 안 사본 (문자열 순서가 같음)
            pn, mem = instr.PAK_MEMBERS[n]
            pk = Pak(files[pn.replace('/', BS)]) if pn.replace('/', BS) in files else Pak(a.read(a.hd6.get(pn)))
            pk.put(mem, instr.apply_by_order(pk.get(mem), a.read(a.hd6.get(n)), tr, to_sjis))
            files[pn.replace('/', BS)] = pk.build()

    # ---- 메뉴 창 폰트 font16 (JIS 배열): 한자 자리에 한글 2,350자
    for n in ('font16.img', '_font16.img', 'img' + BS + 'font16.img', 'img' + BS + 'font16.dat'):
        files[n] = patch_font16(a.read(n), charmap())

    # ---- 실행 파일·오버레이 SJIS 문자열 (font16으로 그려짐: 공백은 그대로)
    def plain_sjis(text):
        out = bytearray()
        for ch in text:
            c = char_code(ch)
            out += bytes([c]) if c < 0x100 else bytes([c >> 8, c & 0xff])
        return bytes(out)

    isofiles = {}
    for f in ELF_FILES:
        data = bytearray(read_iso_file(f))
        for key, text in elf_tr[f].items():
            off = int(key, 16)
            end = data.index(b'\0', off)
            b = (to_sjis if f != 'SLPM_658.88' else plain_sjis)(text)
            assert len(b) <= end - off, ('ELF 문자열 초과', f, key, text)
            data[off:end] = b + b'\0' * (end - off - len(b))
        if f == 'SLPM_658.88':
            namepad.patch(data, plain_sjis)
            if VOICE_MODE:                      # 개인용 음성판 전용 (공개 저장소에는 없는 모듈)
                import voicehook
                voicehook.patch(data)
        isofiles[f] = bytes(data)

    if MISSING:
        print('표에 없어 ■로 바꾼 글자:', MISSING)
    isopatch.patch(out_iso, files, isofiles=isofiles)
    if VOICE_MODE:
        import isovoice
        lba, end = isovoice.add_voice(out_iso, voice_files)
        print('VOICE %d files, ISO %d sectors (%.2f GB)' % (len(voice_files), end, end * 2048 / 1e9))


if __name__ == '__main__':
    main(*sys.argv[1:])
