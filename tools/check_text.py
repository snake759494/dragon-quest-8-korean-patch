"""번역 검사: 한자·가나 잔존(치환 토큰 제외), KS X 1001 밖 글자, 줄 폭(원문 최대 폭 기준)."""
import os, re, glob, sys
from extract import read_tsv
from charset import charmap, is_hangul

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKENS = ['○強主○', '○優主○', '○先頭○', '○ボーイ○', '[アイテム１]', '[アイテム２]']
TAG = re.compile(r'<[a-z_0-9]+>|\{[0-9a-f]{4}\}|\[数値[１-９0-9]\]|\[アイテム[１-９0-9]\]|\[文字列[１-９0-9]\]')


def width(line):
    return sum(1 if ord(c) < 128 else 2 for c in line)


def strip(t):
    for k in TOKENS:
        t = t.replace(k, '')
    return TAG.sub('', t)


def main():
    errs = 0
    pat = sys.argv[1] if len(sys.argv) > 1 else ''
    for ko in glob.glob(os.path.join(ROOT, 'translation', 'ko', '**', '*.tsv'), recursive=True):
        if pat not in ko.replace(os.sep, '/'):
            continue
        jp = ko.replace(os.sep + 'ko' + os.sep, os.sep + 'jp' + os.sep)
        jrows = dict(read_tsv(jp))
        jmax = max([width(strip(l)) for v in jrows.values() for l in v.split('\n')] or [40])
        for k, v in read_tsv(ko):
            t = strip(v)
            if re.search(r'[぀-ヿ一-鿿]', t):
                print('일본어 잔존', ko, k); errs += 1
            for ch in t:
                if is_hangul(ch) and ch not in charmap():
                    print('KS X 1001 밖 글자', ch, ko, k); errs += 1
            lim = jmax
            if os.sep + 'event' + os.sep not in ko and k in jrows:     # 메뉴·주민: 메시지별 원문 폭
                lim = max([width(strip(l)) for l in jrows[k].split('\n')] + [8])
                if len(t.split('\n')) > len(jrows[k].split('\n')):
                    print('줄 수 초과', ko, k); errs += 1
                if TAG.findall(v) != TAG.findall(jrows[k]):
                    print('제어코드 불일치', ko, k); errs += 1
            for l in t.split('\n'):
                if width(l) > lim:
                    print('폭 초과 %d>%d' % (width(l), lim), ko, k, l); errs += 1
    print('오류', errs)


if __name__ == '__main__':
    main()
