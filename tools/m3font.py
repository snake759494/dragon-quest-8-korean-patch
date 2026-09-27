"""지명 글꼴 m3 (meswin\\fonttbl_m3.bin + font_tex_m3.pak) 한글판.

지도 제목·지역 진입 표시 등 지명이 이 글꼴로 그려진다. 원본은 ASCII 88자 + 가나·지명용 한자 148자.
FontTex_m3_0.tm2: 512x416 4bpp, 24x26 칸 21열, 한 장에 294칸(21x14)만 쓴다(나머지 텍스처는 빈 파일).
한글판 = ASCII 88 + 전각 기호·숫자(원본 그대로) + 화면에 나오는 지명(건물 안 '：' 이름·개발용 제외)의 한글.
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
DEV = ('전투', '테스트', '수정', '이벤트', '디버그', 'fld', '（')
TTF = 'NanumSquareNeo-cBd.ttf'


def display_names():
    rows = read_tsv(os.path.join(ROOT, 'translation', 'ko', 'map', 'mapnames.tsv'))
    return [k for _, k in rows if '：' not in k and not any(d in k for d in DEV)]


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
    keep = codes[:na] + [c for c in codes[na:nn] if not (0x829F <= c <= 0x8396)]   # 가나 빼고 기호·숫자
    cm = charmap()
    hang = sorted(set(cm[ch] for k in display_names() for ch in k if '가' <= ch <= '힣'))
    new = keep + hang
    assert len(new) <= PER_PAGE, ('m3 칸 부족', len(new))
    tb = struct.pack('<HHI', na, len(keep), len(new)) + b''.join(struct.pack('>H', c) for c in new)
    pk = Pak(a.read(a.hd6.get('meswin/font_tex_m3.pak')))
    d = bytearray(pk.get('FontTex_m3_0.tm2'))
    src, pix, size = _tim(bytes(d))
    dst = np.zeros_like(src)
    old = {c: i for i, c in enumerate(codes)}
    rev = {v: k for k, v in cm.items()}
    for i, c in enumerate(new):
        _cell(dst, i)[:] = _cell(src, old[c]) if i < len(keep) else _render(rev[c])
    flat = dst.reshape(-1)
    d[pix:pix + size] = ((flat[0::2] & 15) | (flat[1::2] << 4)).astype(np.uint8).tobytes()
    pk.put('FontTex_m3_0.tm2', bytes(d))
    return {'meswin\\fonttbl_m3.bin': tb, 'meswin\\font_tex_m3.pak': pk.build()}, len(hang)


if __name__ == '__main__':
    files, n = build(dq8arc.arc())
    pk = Pak(files['meswin\\font_tex_m3.pak'])
    a, _, _ = _tim(pk.get('FontTex_m3_0.tm2'))
    Image.fromarray((a * 17).astype(np.uint8)).save(os.path.join(ROOT, 'work', 'm3', 'ko.png'))
    print('한글', n)
