"""이름 입력 한글 자모 조합 (두벌식 오토마타) — SLPM_658.88.

게임의 이름 입력: 칸을 고르면 0x2EB570 이 그 칸 글자(2바이트)를 caller 의 192(sp) 에 꺼내고, 점프표
0x3A60A0[0](=0x2EB118)이 이름 버퍼(상태 S=*(gp-25004), 문자열 S+16, 길이 바이트 S+80)에 덧붙인 뒤
0x2EB24C 에서 다시 그린다.  점프표 칸을 COMPOSE 로 바꿔, 입력이 자모면 마지막 글자와 조합한다.

 - 자모 40자(초성 19 + 중성 21)는 2,350 음절 다음 SJIS 칸에 배정 (charset.JAMO).
 - 마지막 글자 상태(코드, 초성 L, 중성 V, 종성 T)는 전역에 두고, 버퍼 마지막 글자가 그 코드와 같을 때만 쓴다.
 - 조합 결과 음절은 '허용 표'(대사·메뉴 두 글꼴에 모두 있는 음절)에 있어야 한다. 없으면 자모를 그냥 덧붙인다.
 - 허용 표 항목 = (유니코드 오프셋 << 16) | KS 순번, 실행 파일의 빈 문자열 자리 여러 곳에 나눠 넣고
   (주소, 개수) 목록으로 찾는다.
"""
import struct
from mips import Asm, R, fva

JAMO_BASE = 2350                  # 자모 순번 = 2350 + j  (j<19 초성, 이후 중성)
LIN0 = (0x88 - 0x81) * 188 + (0x9F - 0x41)   # 0x889F 의 SJIS 선형 번호
S_PTR_GP = -25004
APPEND_ORIG, REDRAW = 0x2EB118, 0x2EB24C
JUMPTAB = 0x3A60A0
DIR_BASE = 0x390000             # 표 조각 주소 기준 (목록에는 (주소-기준)>>2 를 u16 으로)

# 코드 자리 (디버그 출력 전용 문자열 자리, 파일 오프셋)
CODE_CAVE = (0x2AAC20, 472)
HELP_CAVE = (0x296CE8, 224)
DATA_CAVE = (0x2A88C0, 288)
VOWEL_CAVE = (0x2987B0, 416)
TAIL_CAVE = (0x29F450, 240)
SYL_CAVE = (0x29D3B0, 256)

CHO2JONG = [1, 2, 4, 7, 0, 8, 16, 17, 0, 19, 20, 21, 22, 0, 23, 24, 25, 26, 27]
DBLFIN = [(1, 9, 3), (4, 12, 5), (4, 18, 6), (8, 0, 9), (8, 6, 10), (8, 7, 11), (8, 9, 12), (8, 16, 13),
          (8, 17, 14), (8, 18, 15), (17, 9, 18)]
SPLIT = {3: (1, 9), 5: (4, 12), 6: (4, 18), 9: (8, 0), 10: (8, 6), 11: (8, 7), 12: (8, 9), 13: (8, 16),
         14: (8, 17), 15: (8, 18), 18: (17, 9),
         1: (0, 0), 2: (0, 1), 4: (0, 2), 7: (0, 3), 8: (0, 5), 16: (0, 6), 17: (0, 7), 19: (0, 9), 20: (0, 10),
         21: (0, 11), 22: (0, 12), 23: (0, 14), 24: (0, 15), 25: (0, 16), 26: (0, 17), 27: (0, 18)}
CMPV = [(8, 0, 9), (8, 1, 10), (8, 20, 11), (13, 4, 14), (13, 5, 15), (13, 20, 16), (18, 20, 19)]


class A(Asm):
    def r3(self, fn, rd, rs, rt): self.w(R[rs] << 21 | R[rt] << 16 | R[rd] << 11 | fn)
    def addu(self, rd, rs, rt): self.r3(0x21, rd, rs, rt)
    def subu(self, rd, rs, rt): self.r3(0x23, rd, rs, rt)
    def or_(self, rd, rs, rt): self.r3(0x25, rd, rs, rt)
    def slt(self, rd, rs, rt): self.r3(0x2a, rd, rs, rt)
    def sll(self, rd, rt, sa): self.w(R[rt] << 16 | R[rd] << 11 | sa << 6)
    def srl(self, rd, rt, sa): self.w(R[rt] << 16 | R[rd] << 11 | sa << 6 | 2)
    def andi(self, rt, rs, imm): self.i(0xc, rs, rt, imm)
    def ori(self, rt, rs, imm): self.i(0xd, rs, rt, imm)
    def sltiu(self, rt, rs, imm): self.i(0xb, rs, rt, imm)
    def slti(self, rt, rs, imm): self.i(0xa, rs, rt, imm)
    def lb(self, rt, off, rs): self.i(0x20, rs, rt, off)
    def lh(self, rt, off, rs): self.i(0x21, rs, rt, off)
    def lhu(self, rt, off, rs): self.i(0x25, rs, rt, off)
    def sh(self, rt, off, rs): self.i(0x29, rs, rt, off)
    def div(self, rs, rt): self.w(R[rs] << 21 | R[rt] << 16 | 0x1a)
    def mult(self, rs, rt): self.w(R[rs] << 21 | R[rt] << 16 | 0x18)
    def mflo(self, rd): self.w(R[rd] << 11 | 0x12)
    def mfhi(self, rd): self.w(R[rd] << 11 | 0x10)
    def jr(self, rs): self.w(R[rs] << 21 | 8)
    def li(self, rt, v): self.addiu(rt, 'zero', v)

    def _b1(self, op, rs, lab):
        self.fix.append((len(self.code), lab))
        self.i(op, rs, 'zero', 0)
    def blez(self, rs, lab): self._b1(6, rs, lab)
    def bgtz(self, rs, lab): self._b1(7, rs, lab)

    def bgez(self, rs, lab):
        self.fix.append((len(self.code), lab))
        self.w(1 << 26 | R[rs] << 21 | 1 << 16)

    def jal_l(self, lab):
        self.jfix = getattr(self, 'jfix', [])
        self.jfix.append((len(self.code), lab))
        self.w(3 << 26)

    def j_l(self, lab):
        self.jfix = getattr(self, 'jfix', [])
        self.jfix.append((len(self.code), lab))
        self.w(2 << 26)


def lo(x):
    return x - (((x + 0x8000) >> 16) << 16)


def hi(x):
    return (x + 0x8000) >> 16


class Layout:
    """세 코드 자리에 나눠 조립: 라벨이 다른 자리에 있어도 되도록 두 번 조립"""


def assemble(data_va, dir_va):
    """-> {(file_off): bytes}, entry_va"""
    G = data_va                      # +0 lastcode u16, +2 L s8, +3 V s8, +4 T u8
    T_CHO2JONG = G + 8               # 19
    T_DBLFIN = G + 28                # 11*3 = 33 -> 끝 표시 0xff
    T_SPLIT = G + 64                 # 28*2
    T_CMPV = G + 120                 # 7*3 + 끝 표시
    labels = {}
    out = {}
    for _ in range(2):
        pieces = []
        # ---------------- 도움 함수 (HELP_CAVE)
        h = A(fva(HELP_CAVE[0]))
        # CODE(a0 = 순번) -> v0 = SJIS 코드
        h.label('CODE')
        h.addiu('a0', 'a0', LIN0)
        h.li('a1', 188)
        h.div('a0', 'a1')
        h.mflo('v1'); h.mfhi('a1')
        h.addiu('v1', 'v1', 0x81)
        h.sltiu('a2', 'v1', 0xA0)
        h.bne('a2', 'zero', 'c1'); h.addiu('a1', 'a1', 0x40)
        h.addiu('v1', 'v1', 0x40)
        h.label('c1')
        h.sltiu('a2', 'a1', 0x7F)
        h.bne('a2', 'zero', 'c2'); h.sll('v1', 'v1', 8)
        h.addiu('a1', 'a1', 1)
        h.label('c2')
        h.jr('ra'); h.or_('v0', 'v1', 'a1')
        # LIN(a0 = SJIS 코드) -> v0 = 순번 (0x889F 기준)
        h.label('LIN')
        h.srl('v1', 'a0', 8); h.andi('a1', 'a0', 0xff)
        h.sltiu('a2', 'v1', 0xE0)
        h.bne('a2', 'zero', 'l1'); h.addiu('v1', 'v1', -0x81)
        h.addiu('v1', 'v1', -0x40)
        h.label('l1')
        h.sltiu('a2', 'a1', 0x80)
        h.bne('a2', 'zero', 'l2'); h.addiu('a1', 'a1', -0x40)
        h.addiu('a1', 'a1', -1)
        h.label('l2')
        h.li('a2', 188)
        h.mult('v1', 'a2'); h.mflo('v1')
        h.addu('v0', 'v1', 'a1')
        h.jr('ra'); h.addiu('v0', 'v0', -LIN0)
        # SYL(a0=L, a1=V, a2=T) -> v0 = 허용 음절의 SJIS 코드, 없으면 0
        pieces.append((HELP_CAVE, h))
        # SYL(a0=L, a1=V, a2=T) -> v0 = KS X 1001 음절의 SJIS 코드, 없으면 0  (SYL_CAVE)
        # KS 비트맵(유니코드 음절 11,172비트, 여러 조각)에서 비트가 켜져 있으면 앞쪽 켜진 비트 수 = KS 순번
        h = A(fva(SYL_CAVE[0]))
        h.label('SYL')
        h.li('v1', 21)
        h.mult('a0', 'v1'); h.mflo('a0')
        h.addu('a0', 'a0', 'a1')
        h.li('v1', 28)
        h.mult('a0', 'v1'); h.mflo('a0')
        h.addu('a0', 'a0', 'a2')                       # a0 = 유니코드 오프셋 (남은 비트 수)
        h.addiu('sp', 'sp', -16)
        h.sd('t1', 0, 'sp'); h.sd('t2', 8, 'sp')
        h.move('v0', 'zero')                           # v0 = 켜진 비트 누계
        h.lui('a3', hi(dir_va)); h.addiu('a3', 'a3', lo(dir_va))
        h.label('s_dir')
        h.lhu('a1', 0, 'a3')                          # 조각 주소 = 0x390000 + (값 << 2)
        h.beq('a1', 'zero', 's_none'); h.lhu('a2', 2, 'a3')  # 바이트 수
        h.sll('a1', 'a1', 2); h.lui('t1', DIR_BASE >> 16); h.addu('a1', 'a1', 't1')
        h.label('s_byte')
        h.lbu('v1', 0, 'a1')
        h.sltiu('t1', 'a0', 8)
        h.bne('t1', 'zero', 's_last'); h.nop()
        h.label('s_pc')                               # 한 바이트 비트 수 더하기
        h.beq('v1', 'zero', 's_pcd'); h.andi('t1', 'v1', 1)
        h.addu('v0', 'v0', 't1')
        h.b('s_pc'); h.srl('v1', 'v1', 1)
        h.label('s_pcd')
        h.addiu('a0', 'a0', -8)
        h.addiu('a2', 'a2', -1)
        h.bgtz('a2', 's_byte'); h.addiu('a1', 'a1', 1)
        h.b('s_dir'); h.addiu('a3', 'a3', 4)
        h.label('s_last')                             # 목표 비트가 이 바이트 안
        h.w(R['a0'] << 21 | R['v1'] << 16 | R['t2'] << 11 | 6)      # srlv t2,v1,a0
        h.andi('t2', 't2', 1)
        h.beq('t2', 'zero', 's_none'); h.li('t1', 1)
        h.w(R['a0'] << 21 | R['t1'] << 16 | R['t1'] << 11 | 4)      # sllv t1,t1,a0
        h.addiu('t1', 't1', -1)
        h.w(R['v1'] << 21 | R['t1'] << 16 | R['v1'] << 11 | 0x24)   # and v1,v1,t1
        h.label('s_pc2')
        h.beq('v1', 'zero', 's_hit'); h.andi('t1', 'v1', 1)
        h.addu('v0', 'v0', 't1')
        h.b('s_pc2'); h.srl('v1', 'v1', 1)
        h.label('s_hit')
        h.ld('t1', 0, 'sp'); h.ld('t2', 8, 'sp')
        h.addiu('sp', 'sp', 16)
        h.j_l('CODE'); h.move('a0', 'v0')              # 꼬리 호출 (ra 그대로)
        h.label('s_none')
        h.ld('t1', 0, 'sp'); h.ld('t2', 8, 'sp')
        h.addiu('sp', 'sp', 16)
        h.jr('ra'); h.move('v0', 'zero')
        pieces.append((SYL_CAVE, h))

        # ---------------- 본체 (CODE_CAVE)
        m = A(fva(CODE_CAVE[0]))
        m.label('COMPOSE')
        m.lbu('t0', 192, 'sp'); m.lbu('t1', 193, 'sp')
        m.sll('t0', 't0', 8); m.or_('t7', 't0', 't1')           # t7 = 입력 코드
        m.jal_l('LIN'); m.move('a0', 't7')
        m.addiu('t0', 'v0', -JAMO_BASE)                          # t0 = 자모 번호
        m.sltiu('t1', 't0', 40)
        m.beq('t1', 'zero', 'to_orig'); m.lw('t9', S_PTR_GP, 'gp')
        m.lui('t8', hi(G)); m.addiu('t8', 't8', lo(G))           # t8 = 상태
        # 마지막 글자가 상태 코드와 같으면 유효
        m.lh('t2', 80, 't9')                                     # 길이
        m.slti('t1', 't2', 2)
        m.bne('t1', 'zero', 'fresh'); m.addu('t3', 't9', 't2')
        m.lbu('t4', 14, 't3'); m.lbu('t5', 15, 't3')
        m.sll('t4', 't4', 8); m.or_('t4', 't4', 't5')
        m.lhu('t5', 0, 't8')
        m.bne('t4', 't5', 'fresh'); m.nop()
        m.lb('t4', 2, 't8'); m.lb('t5', 3, 't8'); m.lbu('t6', 4, 't8')   # t4=L t5=V t6=T
        m.b('have'); m.nop()
        m.label('fresh')
        m.li('t4', -1); m.li('t5', -1); m.li('t6', 0)
        m.label('have')
        m.sltiu('t1', 't0', 19)
        m.beq('t1', 'zero', 'to_vowel'); m.nop()
        # ----- 자음 t0 (초성 번호)
        m.bltz('t4', 'c_app'); m.nop()
        m.bltz('t5', 'c_app'); m.nop()
        m.bne('t6', 'zero', 'c_dbl'); m.addu('t1', 't8', 't0')
        m.lbu('a2', 8, 't1')                                    # CHO2JONG
        m.beq('a2', 'zero', 'c_app'); m.move('a0', 't4')
        m.move('s3_dummy' if False else 't3', 'a2')
        m.jal_l('SYL'); m.move('a1', 't5')
        m.beq('v0', 'zero', 'c_app'); m.nop()
        m.j_l('replace'); m.sb('t3', 4, 't8')
        m.label('c_dbl')                                        # 겹받침
        m.addiu('t1', 't8', 28)
        m.label('c_dl')
        m.lbu('t2', 0, 't1')
        m.li('t3', 0xff)
        m.beq('t2', 't3', 'c_app'); m.lbu('t3', 1, 't1')
        m.bne('t2', 't6', 'c_dn'); m.nop()
        m.bne('t3', 't0', 'c_dn'); m.nop()
        m.lbu('t3', 2, 't1')
        m.move('a0', 't4'); m.move('a1', 't5')
        m.jal_l('SYL'); m.move('a2', 't3')
        m.beq('v0', 'zero', 'c_app'); m.nop()
        m.j_l('replace'); m.sb('t3', 4, 't8')
        m.label('c_dn')
        m.b('c_dl'); m.addiu('t1', 't1', 3)
        m.label('c_app')                                        # 자음 자모 덧붙이기
        m.sb('t0', 2, 't8'); m.li('t1', -1); m.sb('t1', 3, 't8'); m.sb('zero', 4, 't8')
        m.jal_l('CODE'); m.addiu('a0', 't0', JAMO_BASE)
        m.j_l('append'); m.nop()
        m.label('to_orig')
        m.j_l('orig'); m.nop()
        m.label('to_vowel')
        m.j_l('vowel'); m.nop()
        pieces.append((CODE_CAVE, m))
        # ----- 모음 (VOWEL_CAVE)
        m = A(fva(VOWEL_CAVE[0]))
        m.label('vowel')
        m.addiu('t0', 't0', -19)                                 # t0 = 중성 번호
        m.bltz('t4', 'v_lone'); m.nop()
        m.bgez('t5', 'v_syl'); m.nop()
        # 초성 자모 + 모음 -> 음절
        m.move('a0', 't4'); m.move('a1', 't0')
        m.jal_l('SYL'); m.move('a2', 'zero')
        m.beq('v0', 'zero', 'v_app'); m.nop()
        m.j_l('replace'); m.sb('t0', 3, 't8')
        m.label('v_syl')
        m.bne('t6', 'zero', 'v_split'); m.nop()
        m.jal_l('CMP'); m.nop()                                  # v1 = 겹모음(t5,t0) 또는 -1
        m.bltz('v1', 'v_app'); m.move('t3', 'v1')
        m.move('a0', 't4'); m.move('a1', 't3')
        m.jal_l('SYL'); m.move('a2', 'zero')
        m.beq('v0', 'zero', 'v_app'); m.nop()
        m.j_l('replace'); m.sb('t3', 3, 't8')
        m.label('v_split')                                       # 받침을 다음 음절 초성으로
        m.sll('t1', 't6', 1); m.addu('t1', 't1', 't8')
        m.lbu('t2', 64, 't1'); m.lbu('t3', 65, 't1')             # t2 = 남는 받침, t3 = 넘어갈 초성
        m.move('a0', 't4'); m.move('a1', 't5')
        m.jal_l('SYL'); m.move('a2', 't2')
        m.beq('v0', 'zero', 'v_app'); m.move('t1', 'v0')         # t1 = 앞 음절 코드
        m.move('a0', 't3'); m.move('a1', 't0')
        m.jal_l('SYL'); m.move('a2', 'zero')
        m.beq('v0', 'zero', 'v_app'); m.lh('t2', 80, 't9')
        m.addu('t2', 't2', 't9')                                 # 앞 음절 바꿔 쓰기
        m.srl('t4', 't1', 8); m.sb('t4', 14, 't2'); m.sb('t1', 15, 't2')
        m.sb('t3', 2, 't8'); m.sb('t0', 3, 't8'); m.sb('zero', 4, 't8')
        m.j_l('append'); m.nop()
        m.label('v_lone')
        m.bltz('t5', 'v_app'); m.nop()
        m.jal_l('CMP'); m.nop()
        m.bltz('v1', 'v_app'); m.sb('v1', 3, 't8')
        m.jal_l('CODE'); m.addiu('a0', 'v1', JAMO_BASE + 19)
        m.j_l('replace'); m.nop()
        m.label('v_app')                                         # 모음 자모 덧붙이기
        m.li('t1', -1); m.sb('t1', 2, 't8'); m.sb('t0', 3, 't8'); m.sb('zero', 4, 't8')
        m.jal_l('CODE'); m.addiu('a0', 't0', JAMO_BASE + 19)
        m.j_l('append'); m.nop()
        pieces.append((VOWEL_CAVE, m))
        # ----- 덧붙이기·바꾸기·겹모음 (TAIL_CAVE)
        m = A(fva(TAIL_CAVE[0]))
        m.label('append')
        m.sh('v0', 0, 't8')
        m.srl('t1', 'v0', 8); m.sb('t1', 192, 'sp'); m.sb('v0', 193, 'sp')
        m.label('orig')
        m.j(APPEND_ORIG); m.nop()
        # ----- 마지막 글자 바꾸기: v0 = 코드
        m.label('replace')
        m.sh('v0', 0, 't8')
        m.lh('t2', 80, 't9'); m.addu('t2', 't2', 't9')
        m.srl('t1', 'v0', 8); m.sb('t1', 14, 't2'); m.sb('v0', 15, 't2')
        m.j(REDRAW); m.li('a2', 1)                     # 다시 그리기 인자 (원래 0x2EB23C 에서 설정)
        # ----- CMP: 겹모음 (t5 + t0) -> v1 (없으면 -1)
        m.label('CMP')
        m.addiu('a0', 't8', 120)
        m.label('m_l')
        m.lbu('a1', 0, 'a0')
        m.li('a2', 0xff)
        m.beq('a1', 'a2', 'm_no'); m.lbu('a2', 1, 'a0')
        m.bne('a1', 't5', 'm_n'); m.nop()
        m.bne('a2', 't0', 'm_n'); m.nop()
        m.jr('ra'); m.lbu('v1', 2, 'a0')
        m.label('m_n')
        m.b('m_l'); m.addiu('a0', 'a0', 3)
        m.label('m_no')
        m.jr('ra'); m.li('v1', -1)
        pieces.append((TAIL_CAVE, m))

        # 라벨 모으고 점프 고치기
        for _, a in pieces:
            labels.update(a.labels)
        for cave, a in pieces:
            for k, lab in getattr(a, 'jfix', []):
                t = labels.get(lab, 0)
                a.code[k] = (a.code[k] & 0xfc000000) | ((t >> 2) & 0x3ffffff)
            code = a.assemble()
            assert len(code) <= cave[1], (hex(cave[0]), len(code), cave[1])
            out[cave[0]] = code
    return out, labels['COMPOSE']


def data_block():
    b = bytearray(8)
    struct.pack_into('<Hbbb', b, 0, 0, -1, -1, 0)
    b += bytes(CHO2JONG) + bytes(1)                      # +8 .. +27
    d = bytearray()
    for t in DBLFIN:
        d += bytes(t)
    d += b'\xff'
    b += d.ljust(36, b'\0')                              # +28 .. +63
    s = bytearray()
    for t in range(28):
        s += bytes(SPLIT.get(t, (0, 0)))
    b += s                                               # +64 .. +119
    c = bytearray()
    for t in CMPV:
        c += bytes(t)
    c += b'\xff'
    b += c                                               # +120 ..
    return bytes(b)


def free_runs(elf, exclude):
    """디버그 출력 전용 문자열 자리 (freestr 분석과 같은 기준). exclude: [(시작, 끝)] 파일 오프셋"""
    import re
    import elfstr
    TEXT_END = 0x180 + 2831488
    d = bytes(elf)
    refs, lui = {}, {}
    for o in range(0x180, TEXT_END, 4):
        w = struct.unpack_from('<I', d, o)[0]; op = w >> 26
        if op == 0xf:
            lui[(w >> 16) & 31] = (w & 0xffff, o)
        if op in (9, 0x19) and ((w >> 21) & 31) in lui:
            h, lo_o = lui[(w >> 21) & 31]
            if o - lo_o < 64:
                imm = w & 0xffff; imm -= 0x10000 if imm & 0x8000 else 0
                refs.setdefault((h << 16) + imm, []).append((o, (w >> 16) & 31))

    def printf_only(uses):
        for o, rt in uses:
            if rt != 4:
                return False
            if not any(struct.unpack_from('<I', d, o + 4 * k)[0] == 3 << 26 | 0x14adc0 >> 2 for k in range(-3, 4)):
                return False
        return True
    free = []
    for m in re.finditer(rb'[\x09\x0a\x20-\x7e\x80-\xfc]{4,}\x00{1,16}', d[0x280000:0x2b3000]):
        s = 0x280000 + m.start()
        u = refs.get(s - 0x180 + 0x100000)
        if u and printf_only(u):
            free.append((s, m.end() - m.start()))
    runs, cur = [], None
    for s, n in free:
        if cur and s == cur[0] + cur[1]:
            cur[1] += n
        else:
            if cur:
                runs.append(tuple(cur))
            cur = [s, n]
    if cur:
        runs.append(tuple(cur))
    ok = []
    for s, n in runs:
        a = (s + 3) & ~3
        e = s + n - 1                                    # 마지막 NUL 은 남김
        if any(x < e and a < y for x, y in exclude):
            continue
        if e - a >= 16:
            ok.append((a, (e - a) & ~3))
    return ok


def patch(elf, allowed, charmap):
    """allowed: 허용 음절 문자열 모음 (한글 음절). elf 를 제자리 수정."""
    import charset
    order = sorted(ch for ch in charmap if '가' <= ch <= '힣')
    assert set(allowed) >= set(order), '두 글꼴에 2,350자가 모두 있어야 함 (fontfix)'
    bm = bytearray(11172 // 8 + 1)                      # KS X 1001 음절 비트맵
    for ch in order:
        u = ord(ch) - 0xAC00
        bm[u >> 3] |= 1 << (u & 7)
    exclude = [(0x2A8BF0, 0x2A8CF0), (0x2A8020, 0x2A8130), (0x29D250, 0x29D378),   # 음성판 코드 자리
               (0x2A61F8, 0x2A6218)] + [(c[0], c[0] + c[1]) for c in
                                        (CODE_CAVE, HELP_CAVE, DATA_CAVE, VOWEL_CAVE, TAIL_CAVE, SYL_CAVE)]
    runs = sorted(free_runs(elf, exclude), key=lambda r: -r[1])
    dir_run = runs[-1] if runs[-1][1] >= 64 else next(r for r in runs[::-1] if r[1] >= 64)
    rest = [r for r in runs if r != dir_run]
    dirs, i = [], 0
    for a, n in rest:
        if i >= len(bm):
            break
        k = min(n, len(bm) - i)
        elf[a:a + k] = bm[i:i + k]
        dirs.append((a, k))
        i += k
    assert i == len(bm), ('비트맵 공간 부족', i, len(bm))
    assert 4 * (len(dirs) + 1) <= dir_run[1], ('목록 공간 부족', len(dirs))
    dir_off = dir_run[0]
    dirb = b''.join(struct.pack('<HH', (fva(a) - DIR_BASE) >> 2, k) for a, k in dirs) + bytes(4)
    db = data_block()
    elf[DATA_CAVE[0]:DATA_CAVE[0] + len(db)] = db
    elf[dir_off:dir_off + len(dirb)] = dirb
    code, entry = assemble(fva(DATA_CAVE[0]), fva(dir_off))
    for off, c in code.items():
        elf[off:off + len(c)] = c
    o = JUMPTAB - 0x100000 + 0x180
    assert struct.unpack_from('<I', elf, o)[0] == APPEND_ORIG
    struct.pack_into('<I', elf, o, entry)
    return len(order), len(dirs)


if __name__ == '__main__':
    code, entry = assemble(fva(DATA_CAVE[0]), fva(DATA_CAVE[0]) + 200)
    for k, v in code.items():
        print(hex(k), len(v))
    print(hex(entry), len(data_block()))
