"""실행 파일 문자열 뒤의 정렬용 0 바이트를 늘려 쓰기.

문자열 끝 NUL 뒤에 다음 문자열까지 0 이 이어지면(8·16바이트 정렬 빈자리), 그 사이 주소를
코드(lui+addiu)나 데이터(포인터 표)가 하나도 가리키지 않을 때에 한해 번역문이 그 자리까지 쓸 수 있다.
"""
import struct

_refs = None


def _collect(d):
    refs, lui = set(), {}
    for o in range(0x180, len(d) - 3, 4):
        w = struct.unpack_from('<I', d, o)[0]
        if 0x100000 <= w < 0x400000:
            refs.add(w)
        op = w >> 26
        if op == 0xf:
            lui[(w >> 16) & 31] = (w & 0xffff, o)
        elif op in (9, 0x19) and ((w >> 21) & 31) in lui:
            h, lo = lui[(w >> 21) & 31]
            if o - lo < 64:
                imm = w & 0xffff
                imm -= 0x10000 if imm & 0x8000 else 0
                refs.add((h << 16) + imm)
    return refs


def extend(d, off, end, need):
    """쓸 수 있는 새 끝(파일 오프셋)을 돌려준다. 늘릴 수 없으면 원래 end"""
    global _refs
    if _refs is None:
        _refs = _collect(bytes(d))
    z = end
    while z < len(d) and d[z] == 0:
        z += 1
    lim = end
    for f in range(end + 1, z):                     # 마지막 NUL 하나는 남긴다
        if f - 0x180 + 0x100000 in _refs:
            break
        lim = f
    return lim if lim - off >= need else end
