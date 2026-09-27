"""간단한 MIPS(R5900) 어셈블러와 ELF 주소 변환 (SLPM_658.88: 파일 오프셋 <-> 가상 주소)."""
import struct

R = {n: i for i, n in enumerate(
    'zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split())}


def vo(v):
    return v - 0x100000 + 0x180


class Asm:
    def __init__(self, base):
        self.base, self.code, self.labels, self.fix = base, [], {}, []

    def pc(self):
        return self.base + 4 * len(self.code)

    def label(self, n):
        self.labels[n] = self.pc()

    def w(self, x):
        self.code.append(x & 0xffffffff)

    def i(self, op, rs, rt, imm):
        self.w(op << 26 | R[rs] << 21 | R[rt] << 16 | (imm & 0xffff))

    def nop(self): self.w(0)
    def addiu(self, rt, rs, imm): self.i(9, rs, rt, imm)
    def lui(self, rt, imm): self.i(0xf, 'zero', rt, imm)
    def lbu(self, rt, off, rs): self.i(0x24, rs, rt, off)
    def sb(self, rt, off, rs): self.i(0x28, rs, rt, off)
    def lw(self, rt, off, rs): self.i(0x23, rs, rt, off)
    def sw(self, rt, off, rs): self.i(0x2b, rs, rt, off)
    def sd(self, rt, off, rs): self.i(0x3f, rs, rt, off)
    def ld(self, rt, off, rs): self.i(0x37, rs, rt, off)
    def sq(self, rt, off, rs): self.i(0x1f, rs, rt, off)
    def lq(self, rt, off, rs): self.i(0x1e, rs, rt, off)
    def move(self, rd, rs): self.w(R[rs] << 21 | R[rd] << 11 | 0x2d)
    def jal(self, t): self.w(3 << 26 | (t >> 2) & 0x3ffffff)
    def j(self, t): self.w(2 << 26 | (t >> 2) & 0x3ffffff)
    def swc1(self, ft, off, rs): self.w(0x39 << 26 | R[rs] << 21 | ft << 16 | (off & 0xffff))
    def lwc1(self, ft, off, rs): self.w(0x31 << 26 | R[rs] << 21 | ft << 16 | (off & 0xffff))
    def mov_f12_f0(self): self.w(0x46000306)
    def mtc1_f12(self, rt): self.w(0x44800000 | R[rt] << 16 | 12 << 11)

    def _br(self, op, rs, rt, lab):
        self.fix.append((len(self.code), lab))
        self.i(op, rs, rt, 0)

    def beq(self, rs, rt, lab): self._br(4, rs, rt, lab)
    def bne(self, rs, rt, lab): self._br(5, rs, rt, lab)

    def bltz(self, rs, lab):
        self.fix.append((len(self.code), lab))
        self.w(1 << 26 | R[rs] << 21)

    def b(self, lab): self.beq('zero', 'zero', lab)

    def assemble(self):
        for k, lab in self.fix:
            off = (self.labels[lab] - (self.base + 4 * k + 4)) >> 2
            self.code[k] = (self.code[k] & 0xffff0000) | (off & 0xffff)
        return b''.join(struct.pack('<I', c) for c in self.code)


def fva(file_off):
    return file_off - 0x180 + 0x100000

