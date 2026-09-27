"""font16.img (IM3: font1/font2 1024x1024, font3 1024x256, 4 bpp TIM2) — 메뉴 창용 JIS 배열 폰트.

글리프 = JIS 선형 번호 (구-1)*94 + (점-1), 16x16 칸, 한 줄 64자. font1 = 0..4095, font2 = 4096..
픽셀: 5~15 = 글자(밝기), 1~4 = 그림자 테두리(팔레트상 투명~반투명).
한글은 charmap의 SJIS 코드 -> JIS 위치(한자 자리)에 그린다.
"""
import os, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import binary_dilation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTF = os.path.join(ROOT, 'NanumSquareNeo-cBd.ttf')


def sjis_to_jis_index(c):
    h, l = c >> 8, c & 0xff
    h = (h - 0x81 if h <= 0x9f else h - 0xc1) * 2 + 0x21
    if l >= 0x9f:
        h += 1
        l -= 0x7e
    else:
        l -= 0x1f if l < 0x80 else 0x20
    return (h - 0x21) * 94 + (l - 0x21)


class Font16:
    def __init__(self, data):
        self.d = bytearray(data)
        n = struct.unpack_from('<I', self.d, 8)[0]
        self.pages = []
        for i in range(n):
            off = struct.unpack_from('<I', self.d, 0x10 + 0x40 * i + 0x24)[0]
            tot, clut, img, hs, ncol, fmt, mip, ct, it, w, h = struct.unpack_from('<IIIHHBBBBHH', self.d, off + 0x10)
            pix = off + 0x10 + hs
            px = np.frombuffer(bytes(self.d[pix:pix + img]), np.uint8)
            a = np.empty(w * h, np.uint8)
            a[0::2] = px & 15
            a[1::2] = px >> 4
            self.pages.append((pix, img, a.reshape(h, w)))

    def cell(self, idx):
        page, k = divmod(idx, 4096)
        a = self.pages[page][2]
        y, x = (k // 64) * 16, (k % 64) * 16
        return a[y:y + 16, x:x + 16]

    def build(self):
        for pix, img, a in self.pages:
            f = a.reshape(-1)
            self.d[pix:pix + img] = ((f[0::2] & 15) | (f[1::2] << 4)).astype(np.uint8).tobytes()
        return bytes(self.d)


_font = None


def render16(ch, box=(1, 1, 14, 14)):
    global _font, _box
    if _font is None:
        _font = ImageFont.truetype(TTF, 96)
        ref = Image.new('L', (288, 288))           # 한글 공통 잉크 상자 기준으로 축소
        rd = ImageDraw.Draw(ref)
        for c in '뭘꽉랬뛞훑힘':
            rd.text((96, 96), c, font=_font, fill=255)
        ys, xs = np.nonzero(np.array(ref))
        _box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    bx, by, bw, bh = box
    x0, y0, x1, y1 = _box
    im = Image.new('L', (288, 288))
    dr = ImageDraw.Draw(im)
    dr.text((96, 96), ch, font=_font, fill=255)
    g = np.array(im.crop((x0, y0, x1, y1)).resize((bw, bh), Image.LANCZOS), np.float32) / 255
    cov = np.zeros((16, 16), np.float32)
    cov[by:by + bh, bx:bx + bw] = g
    out = np.zeros((16, 16), np.uint8)
    halo = binary_dilation(cov > 0.25, iterations=1)
    out[halo] = 4
    fill = cov > 0.12
    out[fill] = np.clip(np.round(5 + cov[fill] * 10), 5, 15).astype(np.uint8)
    return out


def patch_font16(data, charmap):
    f = Font16(data)
    for ch, code in charmap.items():
        f.cell(sjis_to_jis_index(code))[:] = render16(ch)
    return f.build()
