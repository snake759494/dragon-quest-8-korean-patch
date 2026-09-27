"""8bpp TIM2(IM3 안) <-> RGBA 이미지. CLUT 256색 RGBA32, PS2 CSM1 배열(32개 단위로 8~15 <-> 16~23 교환), 알파 0~128."""
import struct
import numpy as np
from PIL import Image


def _unswizzle(i):
    return (i & ~0x18) | ((i & 0x08) << 1) | ((i & 0x10) >> 1)


def swz8_index(w, h):
    """PSMT8 스위즐: 선형 (y,x) -> 파일 바이트 위치"""
    y, x = np.mgrid[0:h, 0:w]
    block = (y & ~0xf) * w + (x & ~0xf) * 2
    swap = (((y + 2) >> 2) & 1) * 4
    posy = (((y & ~3) >> 1) + (y & 1)) & 7
    col = posy * w * 2 + ((x + swap) & 7) * 4
    byte = ((y >> 1) & 1) + ((x >> 2) & 2)
    return block + col + byte


def im3_entries(d):
    n = struct.unpack_from('<I', d, 8)[0]
    out = []
    for i in range(n):
        b = 0x10 + 0x40 * i
        out.append((d[b:b + 0x20].split(b'\0')[0].decode(), struct.unpack_from('<I', d, b + 0x24)[0]))
    return out


def info(d, off):
    tot, clut, img, hs, ncol, fmt, mip, ct, it, w, h = struct.unpack_from('<IIIHHBBBBHH', d, off + 0x10)
    assert it == 5 and ncol == 256
    pix = off + 0x10 + hs
    return w, h, pix, pix + img


def palette(d, pal_off):
    raw = np.frombuffer(d[pal_off:pal_off + 1024], np.uint8).reshape(256, 4).copy()
    pal = np.zeros_like(raw)
    for i in range(256):
        pal[i] = raw[_unswizzle(i)]
    return pal


def to_rgba(d, off):
    w, h, pix, pal_off = info(d, off)
    raw = np.frombuffer(d[pix:pix + w * h], np.uint8)
    idx = raw[swz8_index(w, h)]
    pal = palette(d, pal_off).astype(np.uint16)
    a = pal[:, 3] * 255 // 128
    rgba = np.stack([pal[:, 0], pal[:, 1], pal[:, 2], np.minimum(a, 255)], 1).astype(np.uint8)
    return Image.fromarray(rgba[idx], 'RGBA')


def from_rgba(d, off, im):
    """RGBA 이미지를 256색으로 줄여 같은 자리에 다시 쓴다"""
    d = bytearray(d)
    w, h, pix, pal_off = info(d, off)
    im = im.convert('RGBA').resize((w, h))
    q = im.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
    idx = np.array(q, np.uint8)
    p = q.getpalette('RGBA')[:1024]
    p += [0] * (1024 - len(p))
    pal = np.array(p, np.uint8).reshape(256, 4)
    pal[:, 3] = (pal[:, 3].astype(np.uint16) * 128 // 255).astype(np.uint8)
    raw = np.zeros_like(pal)
    for i in range(256):
        raw[_unswizzle(i)] = pal[i]
    out = np.zeros(w * h, np.uint8)
    out[swz8_index(w, h)] = idx
    d[pix:pix + w * h] = out.tobytes()
    d[pal_off:pal_off + 1024] = raw.tobytes()
    return bytes(d)
