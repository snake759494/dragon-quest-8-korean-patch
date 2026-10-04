"""지명 글꼴 m3 (meswin\\fonttbl_m3.bin + font_tex_m3.pak) 한글판.

지도 제목·지역 진입 표시 등 지명이 이 글꼴로 그려진다. 원본은 ASCII 88자 + 가나·지명용 한자 148자.
FontTex_m3_0.tm2: 512x416 4bpp, 24x26 칸 21열, 한 장에 294칸(21x14). 원본은 한 장만 쓰고 _1·_2 는 빈 파일(둘째 장을 채우면 지도 화면에서 멈춤).
한글판 = ASCII 88 + 전각 기호·숫자(원본 그대로) + 지명(개발용 제외)의 한글.
"""
import os, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import dq8arc
from formats import Pak
from charset import charmap
from extract import read_tsv

ROOT = dq8arc.ROOT
CW, CH, COLS, PER_PAGE = 24, 26, 21, 21 * 14
DEV = ('전투', '테스트', '수정', '이벤트', '디버그', 'fld', '필드', '월드맵')
TTF = 'NanumSquareNeo-cBd.ttf'


def display_names():
    rows = read_tsv(os.path.join(ROOT, 'translation', 'ko', 'map', 'mapnames.tsv'))
    return [k for _, k in rows if not any(d in k for d in DEV)]


def _tim(d):
    tot, clut, img, hs, ncol, fmt, mip, ct, it, w, h = struct.unpack_from('<IIIHHBBBBHH', d, 0x10)
    assert it == 4
    px = np.frombuffer(d[0x10 + hs:0x10 + hs + img], np.uint8)
    a = np.empty(w * h, np.uint8)
    a[0::2] = px & 15
    a[1::2] = px >> 4
    return a.reshape(h, w), 0x10 + hs, img


def _cell(a, i):
    y, x = (i // COLS) * CH, (i % COLS) * CW
    return a[y:y + CH, x:x + CW]


def _render(ch):
    px = 96
    f = ImageFont.truetype(os.path.join(ROOT, TTF), px)
    im = Image.new('L', (px * 3, px * 3))
    dr = ImageDraw.Draw(im)
    for c in '뭘꽉랬뛞훑힘':                       # 한글 공통 글자틀
        dr.text((px, px), c, font=f, fill=255)
    ys, xs = np.nonzero(np.array(im))
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    im = Image.new('L', (px * 3, px * 3))
    ImageDraw.Draw(im).text((px, px), ch, font=f, fill=255)
    g = im.crop(box).resize((22, 23), Image.LANCZOS)
    out = np.zeros((CH, CW), np.uint8)
    out[1:24, 1:23] = np.clip(np.round(np.array(g, np.float32) / 255 * 15), 0, 15).astype(np.uint8)
    return out


def build(a):
    t = a.read(a.hd6.get('meswin/fonttbl_m3.bin'))
    na, nn, tot = struct.unpack_from('<HHI', t, 0)
    codes = [struct.unpack_from('>H', t, 8 + 2 * i)[0] for i in range(tot)]
    # 한 장(294칸)에 맞춘다. 둘째 장을 쓰면 글꼴 묶음이 원본보다 커져 지도 화면에서 멈춘다.
    # ASCII 는 숫자·대문자·공백과 지명에 쓰인 문자만, 전각은 가나만 빼고 그대로.
    names = display_names()
    used = set(ch for k in names for ch in k)
    asc = [c for c in codes[:na] if chr(c).isdigit() or chr(c).isupper() or chr(c) == ' ' or chr(c) in used]
    keep = asc + [c for c in codes[na:nn] if not (0x829F <= c <= 0x8396)]
    cm = charmap()
    hang = sorted(set(cm[ch] for k in names for ch in k if '가' <= ch <= '힣'))
    new = keep + hang
    assert len(new) <= PER_PAGE, ('m3 칸 부족', len(new))
    tb = struct.pack('<HHI', len(asc), len(keep), len(new)) + b''.join(struct.pack('>H', c) for c in new)
    pk = Pak(a.read(a.hd6.get('meswin/font_tex_m3.pak')))
    d0 = pk.get('FontTex_m3_0.tm2')
    src, pix, size = _tim(d0)
    old = {c: i for i, c in enumerate(codes)}
    rev = {v: k for k, v in cm.items()}
    for page in range((len(new) + PER_PAGE - 1) // PER_PAGE):   # 294칸 넘으면 둘째 장(원본은 빈 파일)
        d = bytearray(d0)
        dst = np.zeros_like(src)
        for j, c in enumerate(new[page * PER_PAGE:(page + 1) * PER_PAGE]):
            i = page * PER_PAGE + j
            _cell(dst, j)[:] = _cell(src, old[c]) if i < len(keep) else _render(rev[c])
        flat = dst.reshape(-1)
        d[pix:pix + size] = ((flat[0::2] & 15) | (flat[1::2] << 4)).astype(np.uint8).tobytes()
        pk.put('FontTex_m3_%d.tm2' % page, bytes(d))
    return {'meswin\\fonttbl_m3.bin': tb, 'meswin\\font_tex_m3.pak': pk.build()}, len(hang)


if __name__ == '__main__':
    files, n = build(dq8arc.arc())
    pk = Pak(files['meswin\\font_tex_m3.pak'])
    a, _, _ = _tim(pk.get('FontTex_m3_0.tm2'))
    Image.fromarray((a * 17).astype(np.uint8)).save(os.path.join(ROOT, 'work', 'm3', 'ko.png'))
    print('한글', n)
