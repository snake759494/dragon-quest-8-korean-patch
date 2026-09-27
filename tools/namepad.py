"""이름 입력 문자판(SLPM 0x290430~) -> 첫 판 자모(조합 입력, hanime), 둘째 판 자주 쓰는 음절.

원본: 판마다 3블록(각 5자 x 6줄, 줄 사이 '\\n'), 히라가나판 0x290430/0x290480/0x2904d0,
가타카나판 0x290520/0x290570/0x2905c0.  둘째 블록 마지막 줄(ー．…？！ / －．…？！)은 부호로 유지.
전환 라벨: 0x290630 'カナ\\n戻る\\n終る...' (히라가나판에 표시), 0x290650 'かな\\n戻る\\n終る...'.
모든 글자는 2바이트 SJIS라 같은 길이로 제자리 교체된다.
"""

# 첫 판: 자모 (hanime 이 앞 글자와 조합). 블록마다 5자 x 6줄, 둘째 블록 여섯째 줄은 부호 줄이라 25칸
_B = '　'
PAGE1 = ('ㄱㄲㄴㄷㄸ' 'ㄹㅁㅂㅃㅅ' 'ㅆㅇㅈㅉㅊ' 'ㅋㅌㅍㅎ' + _B + _B * 10 +
         'ㅏㅐㅑㅒㅓ' 'ㅔㅕㅖㅗㅘ' 'ㅙㅚㅛㅜㅝ' 'ㅞㅟㅠㅡㅢ' 'ㅣ' + _B * 4 +
         _B * 30)
PAGE2 = ('아안알야양어언에엘여연영예오옥온완요용우운울웅원위유윤은을음의이인일임'
         '자재전정제조종주준중지진찬창채천철초최춘치카케코키타태테토투트티파페포프피하한해혁현호홍화환후훈희히')

BLOCKS = [(0x290430, 0x290480, 0x2904d0), (0x290520, 0x290570, 0x2905c0)]
LABELS = [(0x290630, '다음\n지움\n완료'), (0x290650, '이전\n지움\n완료')]
# 선택한 라벨 칸을 이 문자열들과 비교해 기능을 정한다(カナ/かな/戻る/終る) -> 라벨과 같은 글자로
COMMANDS = [(0x2a61f8, '다음'), (0x2a6200, '이전'), (0x2a6208, '지움'), (0x2a6210, '완료')]
PUNCT_ROW = (1, 5)   # 둘째 블록(1)의 여섯째 줄(5)은 부호 유지


def cells(page_chars):
    chars = list(page_chars)
    out = []
    for b in range(3):
        rows = []
        for r in range(6):
            if (b, r) == PUNCT_ROW:
                rows.append(None)
                continue
            row = ''.join(chars.pop(0) if chars else '　' for _ in range(5))
            rows.append(row)
        out.append(rows)
    return out, chars


def patch(elf, to_sjis):
    """elf: bytearray of SLPM; to_sjis: 한글 -> SJIS 바이트 함수"""
    used = set()
    for page, blocks in zip((PAGE1, PAGE2), BLOCKS):
        layout, rest = cells(page)
        assert not rest, 'too many syllables on a page: %d' % len(rest)
        for base, rows in zip(blocks, layout):
            p = base
            for r, row in enumerate(rows):
                if row is None:
                    p += 11
                    continue
                b = to_sjis(row)
                assert len(b) == 10
                elf[p:p + 10] = b
                used.update(ch for ch in row if ch != '　')
                p += 11
    for off, text in LABELS:
        b = to_sjis(text)
        orig_end = elf.index(b'\0', off)
        assert len(b) <= orig_end - off
        elf[off:off + len(b)] = b
    for off, text in COMMANDS:
        b = to_sjis(text)
        assert len(b) == 4 and elf[off + 4] == 0
        elf[off:off + 4] = b
    return used


ALL = (set(PAGE1) | set(PAGE2)) - {'　'}
