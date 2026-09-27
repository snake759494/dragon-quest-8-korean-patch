"""신조(새) 비행 조작 설명 그림(chara\bird_dat.pac 안 IM3 'torisetsu', 8bpp 512x448)의 일본어 글자를 한글로.

글자 자리만 지우고 원본처럼 밝은 회색 글자 + 오른쪽 아래 어두운 그림자로 다시 그린다.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import dq8arc
from tim8 import im3_entries, to_rgba, from_rgba

ROOT = dq8arc.ROOT
TTF = os.path.join(ROOT, 'NanumSquareNeo-dEb.ttf')
NAME = 'chara' + chr(92) + 'bird_dat.pac'
IM3 = 0x685E0
# (지울 상자 x0,y0,x1,y1, 한글, 정렬)
LABELS = [
    ((124, 24, 166, 52), '하강', 'c'),
    ((24, 88, 94, 114), '좌회전', 'r'),
    ((194, 88, 266, 114), '우회전', 'l'),
    ((116, 112, 174, 127), '왼쪽 스틱', 'c'),
    ((126, 152, 164, 178), '상승', 'c'),
    ((368, 40, 488, 64), '스피드 업', 'l'),
    ((416, 88, 488, 114), '조작 설명', 'l'),
    ((386, 118, 488, 142), '착지하기', 'l'),
    ((366, 152, 450, 178), '지도 보기', 'l'),
    ((102, 280, 190, 306), '착륙 가능', 'c'),
    ((318, 280, 420, 306), '착륙 불가', 'c'),
]


def _label(t, h):
    f = ImageFont.truetype(TTF, h * 4)
    im = Image.new('RGBA', (h * 4 * (len(t) + 2), h * 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((h * 4, h * 2), t, font=f, fill=(230, 230, 230, 255))
    im = im.crop(im.getbbox())
    g = im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)
    out = Image.new('RGBA', (g.width + 2, h + 2), (0, 0, 0, 0))
    sh = Image.new('RGBA', g.size, (10, 10, 30, 255))
    sh.putalpha(g.getchannel('A'))
    out.alpha_composite(sh, (2, 2))
    out.alpha_composite(g, (0, 0))
    return out


def patch_image(im):
    a = np.array(im.convert('RGBA'))
    for (x0, y0, x1, y1), _, _ in LABELS:
        a[y0:y1, x0:x1] = 0
    out = Image.fromarray(a, 'RGBA')
    for (x0, y0, x1, y1), t, al in LABELS:
        h = (y1 - y0) - 8 if y1 - y0 > 20 else (y1 - y0) - 3
        g = _label(t, h)
        if g.width > x1 - x0:
            g = g.resize((x1 - x0, g.height), Image.LANCZOS)
        x = {'l': x0, 'r': x1 - g.width, 'c': (x0 + x1 - g.width) // 2}[al]
        out.alpha_composite(g, (x, (y0 + y1 - g.height) // 2))
    return out


def build():
    d = bytearray(dq8arc.read(NAME))
    sub = bytes(d[IM3:])
    for name, off in im3_entries(sub):
        if name == 'torisetsu':
            new = from_rgba(sub, off, patch_image(to_rgba(sub, off)))
            d[IM3:] = new
    return {NAME: bytes(d)}


if __name__ == '__main__':
    d = build()[NAME]
    sub = d[IM3:]
    for name, off in im3_entries(sub):
        if name == 'torisetsu':
            im = to_rgba(sub, off)
    bg = Image.new('RGBA', im.size, (40, 60, 120, 255))
    bg.alpha_composite(im)
    bg.resize((1024, 896), Image.NEAREST).save(os.path.join(ROOT, 'work', 'fly', 'ko.png'))
