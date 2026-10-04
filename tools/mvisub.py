"""동영상 속 대화창 자막(엔딩 STAFF·URA, 트로데인 회상 602_2)을 한글로.

대화창 안 글자 픽셀을 지우고(inpaint) 한글 대사를 그린 뒤, 대화창이 있는 GOP 만 제자리 재인코딩한다.
글자가 한 자씩 찍히고 줄이 올라가는 연출은 따라 하지 않고, 대사마다 완성된 문장을 보여 준다
(전환 프레임은 다음 대사로).
"""
import os, re
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import dq8arc, mvi, mvienc
from extract import read_tsv

ROOT = dq8arc.ROOT
TTF = os.path.join(ROOT, 'NanumSquareNeo-cBd.ttf')
W, H = mvienc.W, mvienc.H


def ev(path, key):
    t = dict(read_tsv(os.path.join(ROOT, 'translation', 'ko', 'event', path + '.tsv')))[key]
    return re.sub(r'<[^>]*>', '', t)


MITIA = ('e1800/e1803/e1803_4', '1000')
# 파일: (대화창 상자, [(구간 시작, 끝, [대사...])])
MOVIES = {
    'STAFF': [(1480, 1560, [MITIA]),
              (13250, 13960, [('e1800/e1803/e1803_5', k) for k in ('1000', '1010', '1020', '1030', '1040', '1050')])],
    'URA': [(1235, 1315, [MITIA]),
            (13250, 14040, [('e1800/e1804/e1804_5', k) for k in ('1000', '1010', '1020', '1030', '1040', '1050', '1060')])],
    '602_2': [(10, 270, [('e600/e602/e602_2', k) for k in ('420', '430')]),
              (600, 700, [('e600/e602/e602_2', '440')])],
}
BOX = {'': (33, 321, 478, 421)}


def box_on(f, box):
    x0, y0, x1, y1 = box
    g = f.mean(2)
    t = g[y0, x0 + 5:x1 - 5]; b = g[y1 - 1, x0 + 5:x1 - 5]; l = g[y0 + 5:y1 - 5, x0]; r = g[y0 + 5:y1 - 5, x1 - 1]
    return min(t.mean(), b.mean(), l.mean(), r.mean()) > 150 and t.std() < 25


def text_mask(f, box):
    x0, y0, x1, y1 = box
    m = np.zeros(f.shape[:2], np.uint8)
    inner = f[y0 + 3:y1 - 3, x0 + 3:x1 - 3].mean(2)
    m[y0 + 3:y1 - 3, x0 + 3:x1 - 3] = (inner > 100).astype(np.uint8) * 255
    return cv2.dilate(m, np.ones((5, 5), np.uint8))


def draw(img, text, box):
    x0, y0, x1, y1 = box
    sc = (x1 - x0) / 445.0
    f = ImageFont.truetype(TTF, 17)
    im = Image.fromarray(img)
    big = Image.new('RGBA', (int(445), 101), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    for i, ln in enumerate(text.split('\n')):
        x = 20
        if ln.startswith('　'):
            x += 30; ln = ln.lstrip('　')
        y = 11 + i * 27
        d.text((x + 1, y + 1), ln, font=f, fill=(0, 0, 0, 255))
        d.text((x, y), ln, font=f, fill=(235, 235, 235, 255))
    if sc != 1:
        big = big.resize((int(round(445 * sc)), 101), Image.LANCZOS)
    im.paste(big, (x0, y0), big)
    return np.array(im)


def segments(on, masks, a, b):
    """구간 [a,b) 안에서 글자가 40프레임 이상 그대로인 부분(= 대사 하나가 다 찍힌 상태)"""
    out, s, prev = [], None, None
    for i in range(a, b):
        if not on.get(i):
            if s is not None and i - s >= 40: out.append((s, i))
            s = None; continue
        m = masks[i]
        if s is None or np.logical_xor(m, prev).mean() > 0.01:
            if s is not None and i - s >= 40: out.append((s, i))
            s = i
        prev = m
    if s is not None and b - s >= 40: out.append((s, b))
    return out


def process(stem, data, box=BOX['']):
    m = mvi.Movie(data)
    gl = mvienc.gops(m.es)
    want = set()                                   # 대화 구간이 걸친 GOP 의 프레임만 메모리에
    idx = 0
    for s, e, n in gl:
        if any(a < idx + n and idx < b for a, b, _ in MOVIES[stem]):
            want.update(range(idx, idx + n))
        idx += n
    frames, arr, on, masks = {}, {}, {}, {}
    total = 0
    for i, fb in enumerate(mvienc.decode(m.es)):
        total += 1
        if i in want:
            frames[i] = fb
            f = arr[i] = np.frombuffer(fb, np.uint8).reshape(H, W, 3)
            on[i] = box_on(f, box)
            masks[i] = (f[box[1] + 5:box[3] - 5, box[0] + 5:box[2] - 5].mean(2) > 170) if on[i] else None
    assert total == sum(g[2] for g in gl), (total, sum(g[2] for g in gl))
    new = {}
    for a, b, lines in MOVIES[stem]:
        segs = segments(on, masks, a, b)
        assert len(segs) == len(lines), (stem, a, b, segs, len(lines))
        for i in range(a, b):
            if not on.get(i):
                continue
            k = next((j for j, (s, e) in enumerate(segs) if i < e), len(segs) - 1)
            f = arr[i].copy()
            f = cv2.inpaint(f, text_mask(f, box), 4, cv2.INPAINT_TELEA)
            new[i] = draw(f, ev(*lines[k]), box)
    es = bytearray(m.es)
    idx = 0
    changed = 0
    for s, e, n in gl:
        if any(i in new for i in range(idx, idx + n)):
            fr = [new[i].tobytes() if i in new else frames[i] for i in range(idx, idx + n)]
            body, q = mvienc.encode_gop(fr, e - s)
            es[s:e] = body + b'\0' * (e - s - len(body))
            changed += 1
        idx += n
    return m.build(bytes(es)), changed, new


FILES = [('MOVIE/602_2.MVI', '602_2'), ('MOVIE/602_2_W.MVI', '602_2'),
         ('MOVIE/STAFF.MVI', 'STAFF'), ('MOVIE/STAFF_W.MVI', 'STAFF'),
         ('MOVIE/EV/URA.MVI', 'URA'), ('MOVIE/EV/URA_W.MVI', 'URA')]
CACHE = os.path.join(ROOT, 'build', 'movie')


def build_all(log=print):
    """{ISO 경로: 바이트}. 대사·이 스크립트가 그대로면 build/movie 캐시를 쓴다"""
    import hashlib
    from elfstr import read_iso_file
    os.makedirs(CACHE, exist_ok=True)
    out = {}
    for path, stem in FILES:
        lines = [ev(*l) for _, _, ls in MOVIES[stem] for l in ls]
        h = hashlib.md5((open(__file__, 'rb').read().decode('utf-8') + '|'.join(lines)).encode('utf-8')).hexdigest()
        fn = os.path.join(CACHE, path.replace('/', '_'))
        if os.path.exists(fn) and open(fn + '.md5').read() == h:
            out[path] = open(fn, 'rb').read()
            continue
        data, n, _ = process(stem, read_iso_file(path))
        open(fn, 'wb').write(data)
        open(fn + '.md5', 'w').write(h)
        log('동영상 %s: GOP %d개 재인코딩' % (path, n))
        out[path] = data
    return out
