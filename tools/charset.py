"""Korean charset for DQ8.

* Every KS X 1001 Hangul syllable (2,350) gets a fixed SJIS kanji code, in KS order from 0x889F
  (translation/charmap.json).  SJIS text (event .txt, .str) is written with these codes.
* The message-window fonts keep a sorted SJIS code table (meswin/fonttbl_*.bin):
    u16 n_ascii(=88), u16 n_nonkanji, u32 n_total, then n_total * u16 (big-endian SJIS; ASCII as 'c',0x20)
  The game loads it into a 4096-byte buffer -> at most 2044 entries.  Glyph i of the table is cell i
  of the font texture, and .mes files store table indices.
  The Korean tables = original ASCII + original non-kanji (symbols, kana) + the Hangul syllables used
  by the translation.  If a table would overflow, kana are dropped first.
"""
import os, json, struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARMAP = os.path.join(ROOT, 'translation', 'charmap.json')

TABLE_MAX = (4096 - 8) // 2       # FontTbl?BinBuff is 4 KB (slti v0,4097 at 0x2efdd8)


def hangul2350():
    return [bytes([hi, lo]).decode('euc-kr') for hi in range(0xb0, 0xc9) for lo in range(0xa1, 0xff)]


def sjis_slots(n):
    out = []
    lead, trail = 0x88, 0x9f
    while len(out) < n:
        out.append(lead << 8 | trail)
        trail += 1
        if trail == 0x7f:
            trail = 0x80
        if trail > 0xfc:
            lead, trail = lead + 1, 0x40
    return out


def make_charmap():
    hs = hangul2350()
    return dict(zip(hs, sjis_slots(len(hs))))


_cm = None
_rev = None


def charmap():
    global _cm, _rev
    if _cm is None:
        if os.path.exists(CHARMAP):
            _cm = {k: int(v, 16) for k, v in json.load(open(CHARMAP, encoding='utf-8')).items()}
        else:
            _cm = make_charmap()
            os.makedirs(os.path.dirname(CHARMAP), exist_ok=True)
            json.dump({h: '%04X' % c for h, c in _cm.items()}, open(CHARMAP, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=0)
        _rev = {v: k for k, v in _cm.items()}
    return _cm


def is_hangul(ch):
    return '가' <= ch <= '힣'


def char_code(ch):
    """SJIS code (int) of one character of Korean text: ASCII -> byte, Hangul -> slot, else cp932"""
    if ord(ch) < 0x80:
        return ord(ch)
    if is_hangul(ch):
        return charmap()[ch]           # KeyError -> syllable outside KS X 1001
    b = ch.encode('cp932')
    if len(b) == 1:                     # 반각 가나·기호(｢｣ 등)
        return b[0]
    return b[0] << 8 | b[1]


def to_sjis(text):
    out = bytearray()
    for ch in text:
        c = char_code(ch)
        out += bytes([c]) if c < 0x100 else bytes([c >> 8, c & 0xff])
    return bytes(out)


def code_char(c):
    """inverse of char_code for display (Hangul slots shown as Hangul)"""
    charmap()
    if c < 0x80:
        return chr(c)
    if c in _rev:
        return _rev[c]
    try:
        return bytes([c >> 8, c & 0xff]).decode('cp932')
    except UnicodeDecodeError:
        return '[%04x]' % c


def from_sjis(b):
    out, i = [], 0
    while i < len(b):
        c = b[i]
        if (0x81 <= c <= 0x9f or 0xe0 <= c <= 0xfc) and i + 1 < len(b):
            out.append(code_char(c << 8 | b[i + 1]))
            i += 2
        else:
            out.append(chr(c))
            i += 1
    return ''.join(out)


# ------------------------------------------------------------------ font tables
class FontTable:
    def __init__(self, data):
        self.n_ascii, self.n_nonkanji, n = struct.unpack_from('<HHI', data)
        self.codes = []
        for i in range(n):
            a, b = data[8 + 2 * i], data[9 + 2 * i]
            self.codes.append(a if i < self.n_ascii else (a << 8 | b))
        self.index = {c: i for i, c in enumerate(self.codes)}

    def build(self):
        out = bytearray(struct.pack('<HHI', self.n_ascii, self.n_nonkanji, len(self.codes)))
        for i, c in enumerate(self.codes):
            out += bytes([c, 0x20]) if i < self.n_ascii else bytes([c >> 8, c & 0xff])
        return bytes(out)

    def chars(self, japanese=True):
        """display characters; japanese=True decodes kanji codes as cp932 instead of Hangul slots"""
        if not japanese:
            return [code_char(c) for c in self.codes]
        return [chr(c) if c < 0x80 else bytes([c >> 8, c & 0xff]).decode('cp932') for c in self.codes]


def is_kana(code):
    return 0x829f <= code <= 0x82f1 or 0x8340 <= code <= 0x8396


def korean_table(orig, hangul_used, capacity):
    """orig: FontTable (Japanese); hangul_used: iterable of Hangul chars; capacity: max glyph cells.
    returns (FontTable, dropped_nonkanji_codes)"""
    cm = charmap()
    hcodes = sorted(cm[h] for h in set(hangul_used))
    limit = min(TABLE_MAX, capacity)
    ascii_ = orig.codes[:orig.n_ascii]
    nonk = orig.codes[orig.n_ascii:orig.n_nonkanji]
    dropped = []
    need = len(ascii_) + len(nonk) + len(hcodes)
    if need > limit:                      # drop kana, least important first (katakana small forms...)
        kana = [c for c in nonk if is_kana(c)]
        k = need - limit
        drop = set(kana[::-1][:k])
        dropped = sorted(drop)
        nonk = [c for c in nonk if c not in drop]
    assert len(ascii_) + len(nonk) + len(hcodes) <= limit, 'font table overflow: %d Hangul' % len(hcodes)
    t = FontTable.__new__(FontTable)
    t.n_ascii = len(ascii_)
    t.n_nonkanji = len(ascii_) + len(nonk)
    t.codes = ascii_ + nonk + hcodes
    t.index = {c: i for i, c in enumerate(t.codes)}
    return t, dropped
