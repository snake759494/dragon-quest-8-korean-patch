"""타이틀 로고(title\\title.img 의 'title'·'title_w')의 일본어 부제 두 줄만 한글로 교체.

로고 그림은 원본 그대로 두고, 부제 영역만 지운 뒤 나눔스퀘어네오 Heavy로
원본처럼 검은 글자 + 흰 테두리로 그린다. title_w(와이드용)는 가로로 눌린 그림이라 영역이 다르다.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import dq8arc
from tim8 import im3_entries, to_rgba, from_rgba

ROOT = dq8arc.ROOT
TTF = os.path.join(ROOT, 'NanumSquareNeo-eHv.ttf')
LEFT = '드래곤퀘스트 VIII'
RIGHT = ('하늘과 바다와 대지와', '저주받은 공주')
# 이미지별 (왼쪽 부제 상자, 오른쪽 부제 상자) = (x0, y0, x1, y1)
BOXES = {
    'title': ((58, 250, 198, 270), (318, 249, 452, 272), (452, 249, 460, 272)),
    'title_w': ((96, 270, 209, 287), (307, 268, 419, 290)),
}


def _text_block(lines, size):
    """흰 테두리 검은 글자 여러 줄을 여유 있게 그린 RGBA (잉크 상자로 잘라서 반환)"""
    f = ImageFont.truetype(TTF, size)
    lh = int(size * 1.15)
    im = Image.new('RGBA', (size * 20, lh * len(lines) + size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, t in enumerate(lines):
        d.text((size, size // 2 + i * lh), t, font=f, fill=(15, 15, 15, 255),
               stroke_width=max(2, size // 7), stroke_fill=(255, 255, 255, 255))
    return im.crop(im.getbbox())


def patch_image(im, name):
    a = np.array(im.convert('RGBA'))
    for x0, y0, x1, y1 in BOXES[name]:
        a[y0 - 2:y1 + 3, x0 - 2:x1 + 3] = 0
    out = Image.fromarray(a, 'RGBA')
    (lx0, ly0, lx1, ly1), (rx0, ry0, rx1, ry1) = BOXES[name][:2]
    left = _text_block([LEFT], 64).resize((lx1 - lx0, ly1 - ly0), Image.LANCZOS)
    right = _text_block(list(RIGHT), 64).resize((rx1 - rx0, ry1 - ry0 + 8), Image.LANCZOS)
    out.alpha_composite(left, (lx0, ly0))
    out.alpha_composite(right, (rx0, ry0 - 2))
    return out


def build():
    d = dq8arc.read('title\\title.img')
    for name, off in im3_entries(d):
        if name in BOXES:
            d = from_rgba(d, off, patch_image(to_rgba(d, off), name))
    return {'title\\title.img': d}


if __name__ == '__main__':
    d = dq8arc.read('title\\title.img')
    ims = []
    for name, off in im3_entries(d):
        if name in BOXES:
            o = to_rgba(d, off)
            k = patch_image(o, name)
            ims += [o, k]
    bg = Image.new('RGBA', (1024, 896), (40, 60, 90, 255))
    for i, im in enumerate(ims):
        bg.alpha_composite(im, ((i % 2) * 512, (i // 2) * 448))
    bg.convert('RGB').save(os.path.join(ROOT, 'work', 'title', 'compare_final.png'))
    # 재양자화 후 결과도 확인
    nd = build()['title\\title.img']
    for name, off in im3_entries(nd):
        if name in BOXES:
            to_rgba(nd, off).save(os.path.join(ROOT, 'work', 'title', name + '_ko_quant.png'))
