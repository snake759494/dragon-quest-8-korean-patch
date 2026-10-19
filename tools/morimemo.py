"""모리의 메모(menu/morimemo0~2.img, 와이드판 *w) 그림의 일본어 글자를 한글로.

투기장 옥상의 모리에게 받는 몬스터 소개 메모 3장. 양피지 위 갈색 글자만 지우고(inpaint, 밑줄은 남김)
같은 자리에 한글을 다시 쓴다. 와이드판은 같은 배치를 가운데(x=256) 기준으로 가로 0.75배 줄인 그림이다.
"""
import os
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import dq8arc
from tim8 import im3_entries, to_rgba, from_rgba

ROOT = dq8arc.ROOT
BS = '\\'
FONT = os.path.join(ROOT, 'NanumSquareNeo-cBd.ttf')
INK = (62, 42, 28, 255)
LABELS = ('전투 타입', '목격 정보', '설명')
MEMOS = {
    'morimemo0': ('에이스슬라임', '스라린', '슬라임',
                  ('말랑말랑 직접 공격형', '멸망한 성 근처에서 목격 정보 있음', '나쁜 슬라임이 아니라고는 못 한다')),
    'morimemo1': ('론리조', '조', '떠도는갑옷',
                  ('검사 직접 공격형', '마이엘라 수도원 주변 둑에서 목격', '고독을 사랑하는 비틀비틀 검사')),
    'morimemo2': ('싱싱꼬맹이', '푸치논', '푸치아논',
                  ('꿈틀꿈틀 직접 공격형', '여도적의 아지트 근처 물가에서 목격', '물가의 개구쟁이 보이')),
}
# 지울 글자 상자 (4:3 판 좌표): 제목, 이름·종족, 표 세 줄
BOXES = [(150, 37, 362, 62), (150, 268, 362, 319), (34, 332, 478, 409)]


def _squeeze(x):
    return int(round(256 + (x - 256) * 0.75))


def _erase(img, wide):
    a = np.array(img.convert('RGB'))
    g = a.mean(2)
    m = np.zeros(g.shape, np.uint8)
    for x0, y0, x1, y1 in BOXES:
        if wide:
            x0, x1 = _squeeze(x0), _squeeze(x1)
        m[y0:y1, x0:x1] = (g[y0:y1, x0:x1] < 120) * 255
    m = cv2.dilate(m, np.ones((3, 3), np.uint8))
    out = cv2.inpaint(a, m, 3, cv2.INPAINT_TELEA)
    rgba = np.array(img.convert('RGBA'))
    rgba[..., :3] = out
    return Image.fromarray(rgba, 'RGBA')


def _text_layer(title, name, kind, rows):
    lay = Image.new('RGBA', (512, 448), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    f = ImageFont.truetype(FONT, 16)
    w = d.textlength(title, font=f)
    d.text((256 - w / 2, 41), title, font=f, fill=INK)
    for y, lab, val in ((272, '이름', name), (297, '종족', kind)):
        d.text((199, y), lab, font=f, fill=INK)
        d.text((240, y), ':' + val, font=f, fill=INK)
    for y, lab, val in zip((337, 362, 387), LABELS, rows):
        d.text((40, y), lab, font=f, fill=INK)
        d.text((146, y), ':' + val, font=f, fill=INK)
    return lay


def patch_image(img, key, wide):
    out = _erase(img, wide)
    lay = _text_layer(*MEMOS[key])
    if wide:
        sq = lay.resize((384, 448), Image.LANCZOS)
        lay = Image.new('RGBA', (512, 448), (0, 0, 0, 0))
        lay.alpha_composite(sq, (64, 0))
    out.alpha_composite(lay)
    return out


def build():
    files = {}
    for key in MEMOS:
        for wide in (False, True):
            n = 'menu' + BS + key + ('w' if wide else '') + '.img'
            d = dq8arc.read(n)
            for nm, off in im3_entries(d):
                d = from_rgba(d, off, patch_image(to_rgba(d, off), key, wide))
            files[n] = d
    return files


if __name__ == '__main__':
    fs = build()
    ims = []
    for n, d in fs.items():
        nm, off = im3_entries(d)[0]
        ims.append(to_rgba(d, off).convert('RGB'))
    sheet = Image.new('RGB', (1024, 448 * 3))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % 2) * 512, (i // 2) * 448))
    sheet.save(os.path.join(ROOT, 'work', 'mori', 'ko.png'))
