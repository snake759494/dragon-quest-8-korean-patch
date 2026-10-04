"""카메라 반전 설정 (SLPM_658.88): 필드 메뉴 '설정'에 '카메라' 항목을 더한다.

일본판 설정 처리(0x204150 부근)는 원래 항목 3개(0 화면 크기, 1 사운드, 2 진동)를 다루게 짜여 있고
메뉴 문구(allmenu9 110)만 두 줄로 줄여 진동을 숨겨 두었다. 숨은 2번 자리를 '카메라'로 쓴다.
- 선택지 문구: allmenu9 100 (원래 빈 메시지, 표 gp-0x7520[2]=0 -> 100). 보통/좌우 반전/상하 반전/모두 반전
- 값: 시스템 설정 구조체 0x3EFAA0(0x30바이트, 세이브에 그대로 저장) 의 +0x24 (bit0 좌우, bit1 상하).
  북미판도 같은 구조체 +0x24/+0x25 에 반전 플래그를 둔다. 예전 세이브는 0 = 보통.
- 적용: 카메라 입력 두 곳(0x1747A4 필드, 0x186C3C 다른 카메라)에서 동굴 코드가 부호를 바꾼다.
  (DQ8_camera_invert 패치(둘 다 반전)와 같은 자리)
"""
import struct
from mips import Asm, fva

CAVE = (0x2A7190, 160)              # 디버그 출력 전용 문자열 자리 (hanime 의 빈자리 목록에서 제외)
CFG_HI, CFG_LO = 0x3F, -0x53C       # 0x3EFAA0 + 0x24


def _o(va):
    return va - 0x100000 + 0x180


def _neg(fd, fs):
    return 0x46000007 | fs << 11 | fd << 6


def _andi(rt, rs, imm):
    from mips import R
    return 0xC << 26 | R[rs] << 21 | R[rt] << 16 | imm


def _lh(rt, off, rs):
    from mips import R
    return 0x21 << 26 | R[rs] << 21 | R[rt] << 16 | (off & 0xffff)


def _put(elf, va, old, new):
    assert struct.unpack_from('<I', elf, _o(va))[0] == old, (hex(va), hex(struct.unpack_from('<I', elf, _o(va))[0]))
    struct.pack_into('<I', elf, _o(va), new)


def _cave():
    a = Asm(fva(CAVE[0]))
    # A: 0x1747A4 의 jal 0x172900 대신. 좌우(f20)에 부호, 0x90(sp) 에 저장한 뒤 원래 함수로
    a.label('A')
    a.lui('t0', CFG_HI); a.lw('t0', CFG_LO, 't0')
    a.w(_andi('t0', 't0', 1))
    a.beq('t0', 'zero', 'A1'); a.nop()
    a.w(_neg(20, 20))
    a.label('A1')
    a.swc1(20, 0x90, 'sp')
    a.j(0x172900); a.nop()
    # B: 0x1747AC. 원래 move a0,s4 + 상하(f1 = -f0) 에 부호
    a.label('B')
    a.lui('t0', CFG_HI); a.lw('t0', CFG_LO, 't0')
    a.w(_andi('t0', 't0', 2))
    a.beq('t0', 'zero', 'B1'); a.move('a0', 's4')
    a.w(_neg(1, 1))
    a.label('B1')
    a.w(0x03E00008); a.nop()                       # jr ra
    # C: 0x186C3C. 상하(f3) / 좌우(f20) 에 부호 (t 레지스터 보존)
    a.label('C')
    a.addiu('sp', 'sp', -16); a.sd('t0', 0, 'sp'); a.sd('t1', 8, 'sp')
    a.lui('t0', CFG_HI); a.lw('t0', CFG_LO, 't0')
    a.w(_andi('t1', 't0', 2))
    a.beq('t1', 'zero', 'C1'); a.w(_andi('t1', 't0', 1))
    a.w(_neg(3, 3))
    a.label('C1')
    a.beq('t1', 'zero', 'C2'); a.nop()
    a.w(_neg(20, 20))
    a.label('C2')
    a.ld('t0', 0, 'sp'); a.ld('t1', 8, 'sp')
    a.w(0x03E00008); a.addiu('sp', 'sp', 16)
    # D: 0x204304 의 jal 0x22D5A0(선택지 커서) 대신. a2(최댓값) = (상태값>>7)|1 -> 화면 크기 1, 카메라 3
    a.label('D')
    a.j(0x22D5A0); a.w(0x34C60001)                 # ori a2,a2,1 (지연 슬롯)
    code = a.assemble()
    assert len(code) <= CAVE[1], len(code)
    return code, a.labels


def patch(elf):
    code, L = _cave()
    s = CAVE[0]
    elf[s:s + len(code)] = code
    J = lambda t: 3 << 26 | (t >> 2) & 0x3ffffff
    # 필드 카메라
    _put(elf, 0x1747A4, J(0x172900), J(L['A']))
    _put(elf, 0x1747A8, 0xE7B40090, 0)              # swc1 f20,0x90(sp) -> nop (A 에서 저장)
    _put(elf, 0x1747AC, 0x46000047, J(L['B']))      # neg.s f1,f0 -> jal B
    _put(elf, 0x1747B0, 0x0280202D, 0x46000047)     # move a0,s4 -> neg.s f1,f0 (지연 슬롯, move 는 B 에서)
    # 다른 카메라
    _put(elf, 0x186C3C, 0x44800000, J(L['C']))      # mtc1 zero,f0 -> jal C
    _put(elf, 0x186C40, 0x00000000, 0x44800000)     # nop -> mtc1 zero,f0 (지연 슬롯)
    # 설정 메뉴: 항목 목록 커서 0~1 -> 0~2
    _put(elf, 0x2041AC, 0x24060001, 0x24060002)     # addiu a2,zero,1 -> 2
    # 상태값(-0x6abc) 300(카메라)도 선택지 창(0x2042F4)으로. 그 밖(0)은 항목 목록(0x2041A0)
    B = lambda at, tgt, rs, rt: 4 << 26 | rs << 21 | rt << 16 | ((tgt - at - 4) >> 2 & 0xffff)
    _put(elf, 0x20418C, 0x00000000, 0x2402012C)     # nop -> addiu v0,zero,300 (지연 슬롯)
    _put(elf, 0x204190, 0x10600003, B(0x204190, 0x2042F4, 3, 2))   # beqz v1 -> beq v1,v0,선택지
    _put(elf, 0x204198, 0x1000009B, 0x00000000)     # b 0x204408 -> nop (목록 코드로 이어짐)
    _put(elf, 0x20419C, 0x0000102D, 0x00000000)     # move v0,zero -> nop
    # 선택지 커서 최댓값: 화면 크기 1(2개), 카메라 3(4개)
    _put(elf, 0x204300, 0x24060001, 0x000331C2)     # addiu a2,zero,1 -> srl a2,v1,7
    _put(elf, 0x204304, 3 << 26 | 0x22D5A0 >> 2, 3 << 26 | (L['D'] >> 2) & 0x3ffffff)
    # 설정 메뉴: 2번 항목 처음 커서 = cfg+0x24
    _put(elf, 0x2042D8, 0x8E230008, 0x8E230024)     # lw v1,8(s1) -> lw v1,0x24(s1)
    # 확인: 2번 항목이면 cfg+0x24, 아니면 cfg+0 에 저장 (진동 확인 진동은 뺌)
    # 0x204370~0x2043A4 (원래: jal 적용 / sw v0,0(s0) / 진동 확인용 진동) 를 다시 쓰고 0x2043A8 로 이어간다
    b = Asm(0x204370)
    b.w(_lh('v1', -0x6ABC, 'gp'))
    b.addiu('a0', 'zero', 0x12C)
    b.bne('v1', 'a0', 'S'); b.nop()
    b.b('P'); b.sw('v0', 0x24, 's0')
    b.label('S'); b.sw('v0', 0, 's0')
    b.label('P'); b.jal(0x184B70); b.nop()
    n = len(b.code)
    off = (0x2043A8 - (0x204370 + 4 * n + 4)) >> 2
    b.w(0x10000000 | (off & 0xffff)); b.nop()            # b 0x2043A8
    blk = b.assemble()
    assert 0x204370 + len(blk) <= 0x2043A8
    o = _o(0x204370)
    orig = struct.unpack_from('<I', elf, o)[0]
    assert orig == 3 << 26 | 0x184B70 >> 2, hex(orig)      # jal 0x184b70
    elf[o:o + len(blk)] = blk
