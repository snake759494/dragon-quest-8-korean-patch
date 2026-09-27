"""bin_ext\\itemana5.txt (아이템 분석: 분류 / 능력치 줄 / 설명) 번역.

형식: 'id_offset=10000' 뒤에 '@번호\\r\\n분류\\r\\n능력치줄\\r\\n설명\\r\\n' 반복 (칸 안 줄바꿈은 \\n).
설명은 itemstr1.lst 의 같은 일본어 문장 번역을 그대로 쓴다(전부 짝이 맞음). 분류·능력치 줄은 아래 표.
"""
import os
import dq8arc
from extract import read_tsv

ROOT = dq8arc.ROOT
TR = os.path.join(ROOT, 'translation')
NAME = 'bin_ext/itemana5.txt'
CATEGORY = {'武器': '무기', 'どうぐ': '도구', 'よろい': '갑옷', '盾': '방패', 'かぶと': '투구',
            '装飾品': '장신구', 'だいじなもの': '소중한 것', 'なし': '없음'}
FIELD2 = {'こうげきりょく\n[文字列１]': '공격력\n[文字列１]',
          'しゅびりょく\n[文字列１]': '수비력\n[文字列１]',
          'すばやさ\n[文字列１]': '민첩성\n[文字列１]',
          'かしこさ\n[文字列１]': '지혜\n[文字列１]',
          '  １かいつかうと\n  なくなる': '  한 번 쓰면\n  없어진다',
          '  ひつようなとき\n  つかおう': '  필요할 때\n  쓰자',
          '　戦闘中に\n　使おう': '　전투 중에\n　쓰자',
          '　錬金釜に\n　入れてみよう': '　연금솥에\n　넣어 보자'}


def _desc_map():
    J = dict(read_tsv(os.path.join(TR, 'jp', 'btl', 'itemstr1.lst.tsv')))
    K = dict(read_tsv(os.path.join(TR, 'ko', 'btl', 'itemstr1.lst.tsv')))
    bs = chr(92)
    return {J[k].replace(bs + 'n', '\n').rstrip('\n'): K[k].replace(bs + 'n', '\n').rstrip('\n') for k in J if k in K}


def texts():
    """폰트 글자 수집용 한국어 문자열"""
    return list(CATEGORY.values()) + list(FIELD2.values()) + list(_desc_map().values())


def build(data, enc):
    """data: 원본 파일, enc: str -> SJIS bytes (한글 매핑). 칸 안 \\n 은 그대로 둔다."""
    dm = _desc_map()
    t = data.decode('cp932')
    ents = t.split('\r\n@')
    out = [ents[0].encode('cp932')]
    for e in ents[1:]:
        f = e.split('\r\n')
        if len(f) > 1 and f[1] in CATEGORY:
            f[1] = CATEGORY[f[1]]
        if len(f) > 2 and f[2] in FIELD2:
            f[2] = FIELD2[f[2]]
        if len(f) > 3 and f[3].rstrip('\n') in dm:
            f[3] = dm[f[3].rstrip('\n')]
        parts = []
        for x in f:                                  # 한글이 든 줄만 한글 매핑, 나머지(번호·[文字列１] 토큰 등)는 원래 SJIS
            parts.append(b'\n'.join(enc(y) if any('가' <= c <= '힣' for c in y) else y.encode('cp932')
                                    for y in x.split('\n')))
        out.append(b'\r\n'.join(parts))
    return b'\r\n@'.join(out)
