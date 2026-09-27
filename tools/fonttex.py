"""Message-window font textures (meswin/font_tex_l3s3.pak).

Cells are 18x22, 28 per row, 17 rows per page (the game computes 512/18 and 380/22).
  l3 (dialogue): 6 pages of 2 bpp packed two per 4 bpp TIM2:
        page 2k = bits 2-3, page 2k+1 = bits 0-1 of FontTex_l3_{2k}{2k+1}.tm2
        glyph box ~16x21 (x 0..16, y 1..21), thin strokes, 4 levels.
  s3 (menus):    3 pages of 4 bpp (FontTex_s3_0/1/2.tm2), glyph box 15x19 (x 0..14, y 1..19), 16 levels.
Glyph i of the font table is cell i (page-major).
"""
import os, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from formats import Pak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CW, CH, COLS, ROWS = 18, 22, 28, 17
PER_PAGE = COLS * ROWS
L3_PAGES = [('FontTex_l3_01.tm2', 2), ('FontTex_l3_01.tm2', 0), ('FontTex_l3_23.tm2', 2),
            ('FontTex_l3_23.tm2', 0), ('FontTex_l3_45.tm2', 2), ('FontTex_l3_45.tm2', 0)]
S3_PAGES = [('FontTex_s3_0.tm2', 0), ('FontTex_s3_1.tm2', 0), ('FontTex_s3_2.tm2', 0)]       # 원본 4bpp
# 한글 확장판: s3 도 l3 처럼 2bpp 페이지 6장 (fontfix 가 게임 쪽을 고침)
S3P_PAGES = [('FontTex_s3_0.tm2', 2), ('FontTex_s3_0.tm2', 0), ('FontTex_s3_1.tm2', 2),
             ('FontTex_s3_1.tm2', 0), ('FontTex_s3_2.tm2', 2), ('FontTex_s3_2.tm2', 0)]
CAPACITY = {'l3': len(L3_PAGES) * PER_PAGE, 's3': len(S3P_PAGES) * PER_PAGE}

# per font: (ttf, box x, box y, box w, box h, levels, bits)
STYLE = {
    'l3': ('NanumSquareNeo-cBd.ttf', 0, 1, 17, 21, 3, 2),
    's3': ('NanumSquareNeo-cBd.ttf', 0, 1, 15, 19, 3, 2),
}


class Tim4:
    """4 bpp TIM2 picture inside a pak item, pixels as (h, w) uint8 array"""

    def __init__(self, data):
        self.d = bytearray(data)
        tot, clut, img, hs, ncol, fmt, mip, ct, it, w, h = struct.unpack_from('<IIIHHBBBBHH', self.d, 0x10)
        assert it == 4
        self.w, self.h, self.pix, self.size = w, h, 0x10 + hs, img
        px = np.frombuffer(bytes(self.d[self.pix:self.pix + img]), np.uint8)
        a = np.empty(w * h, np.uint8)
        a[0::2] = px & 15
        a[1::2] = px >> 4
        self.a = a.reshape(h, w)

    def build(self):
        a = self.a.reshape(-1)
        self.d[self.pix:self.pix + self.size] = ((a[0::2] & 15) | (a[1::2] << 4)).astype(np.uint8).tobytes()
        return bytes(self.d)


class FontPak:
    def __init__(self, data, s3_planar=False):
        """s3_planar: s3 를 2bpp 6페이지로 읽고 쓴다 (원본 파일을 읽을 땐 False)"""
        self.s3_planar = s3_planar
        self.pak = Pak(data)
        self.tex = {n: Tim4(self.pak.get(n)) for n in self.pak.names() if n.endswith('.tm2')
                    and len(self.pak.get(n))}

    def _loc(self, font, i):
        pages = L3_PAGES if font == 'l3' else S3P_PAGES if self.s3_planar else S3_PAGES
        name, sh = pages[i // PER_PAGE]
        k = i % PER_PAGE
        return self.tex[name].a, (k // COLS) * CH, (k % COLS) * CW, sh

    def mask(self, font):
        return 3 if font == 'l3' or self.s3_planar else 15

    def clear(self, font):
        for n, _ in (L3_PAGES if font == 'l3' else S3P_PAGES):
            self.tex[n].a[:] = 0

    def get(self, font, i):
        a, y, x, sh = self._loc(font, i)
        mask = self.mask(font)
        return (a[y:y + CH, x:x + CW] >> sh) & mask

    def put(self, font, i, g):
        a, y, x, sh = self._loc(font, i)
        mask = self.mask(font)
        cell = a[y:y + CH, x:x + CW]
        cell &= ~np.uint8(mask << sh) & 15
        cell |= (np.asarray(g, np.uint8) & mask) << sh

    def build(self):
        for n, t in self.tex.items():
            self.pak.put(n, t.build())
        return self.pak.build()


# ------------------------------------------------------------------ Hangul rendering
_fonts = {}


def _font(ttf, px):
    k = (ttf, px)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(os.path.join(ROOT, ttf), px)
    return _fonts[k]


_em = {}


def _em_box(ttf, px):
    """ink box shared by all Hangul (union of tall/wide syllables) at render size px"""
    k = (ttf, px)
    if k not in _em:
        f = _font(ttf, px)
        im = Image.new('L', (px * 3, px * 3))
        dr = ImageDraw.Draw(im)
        for c in '뭘꽉랬뛞훑힘쀍퓇':
            dr.text((px, px), c, font=f, fill=255)
        ys, xs = np.nonzero(np.array(im))
        _em[k] = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    return _em[k]


def render(ch, font):
    ttf, bx, by, bw, bh, levels, _ = STYLE[font]
    px = 96
    x0, y0, x1, y1 = _em_box(ttf, px)
    im = Image.new('L', (px * 3, px * 3))
    ImageDraw.Draw(im).text((px, px), ch, font=_font(ttf, px), fill=255)
    im = im.crop((x0, y0, x1, y1)).resize((bw, bh), Image.LANCZOS)
    cov = np.array(im, np.float32) / 255
    g = np.zeros((CH, CW), np.uint8)
    g[by:by + bh, bx:bx + bw] = np.clip(np.round(cov * levels), 0, levels).astype(np.uint8)
    return g
