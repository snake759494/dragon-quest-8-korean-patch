"""실행 파일·오버레이(SLPM_658.88, BIN/*.BIN) 안의 SJIS 문자열 찾기 / 제자리 교체.

문자열 = NUL로 끝나는 SJIS 바이트열 중 가나·한자가 1자 이상 있는 것.
교체는 원래 바이트 길이 이하만 허용하고 남는 자리는 NUL로 채운다(포인터는 그대로).
"""
import os, re, pycdlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISO_JP = os.path.join(ROOT, 'Dragon Quest VIII - Sora to Umi to Daichi to Norowareshi Himegimi (Japan, Asia).iso')
FILES = ['SLPM_658.88', 'BIN/TITLE.BIN', 'BIN/MENU.BIN', 'BIN/BATTLE.BIN', 'BIN/CASINO.BIN']

SJ = re.compile(rb'(?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]|[\x20-\x7e\n])+\x00')


def read_iso_file(path, iso=ISO_JP):
    i = pycdlib.PyCdlib()
    i.open(iso)
    import io
    b = io.BytesIO()
    i.get_file_from_iso_fp(b, iso_path='/' + path + ';1')
    i.close()
    return b.getvalue()


def has_jp(s):
    return re.search(r'[぀-ヿ一-鿿]', s) is not None


def find_strings(data):
    out = []
    for m in SJ.finditer(data):
        raw = m.group()[:-1]
        try:
            s = raw.decode('cp932')
        except UnicodeDecodeError:
            continue
        jp = len(re.findall(r'[぀-ヿ一-鿿　-〿！-～]', s))
        if m.start() > 0 and data[m.start() - 1] != 0:
            continue
        if has_jp(s) and jp >= 2 and jp * 2 >= len(s.replace('\n', '')):
            out.append((m.start(), len(raw), s))
    return out


def dump():
    from extract import esc
    os.makedirs(os.path.join(ROOT, 'translation', 'jp', 'elf'), exist_ok=True)
    for f in FILES:
        s = find_strings(read_iso_file(f))
        print(f, len(s), sum(len(x[2]) for x in s))
        with open(os.path.join(ROOT, 'translation', 'jp', 'elf', f.replace('/', '_') + '.tsv'), 'w',
                  encoding='utf-8', newline='\n') as o:
            for off, n, t in s:
                o.write('%06x\t%s\n' % (off, esc(t)))


if __name__ == '__main__':
    dump()
