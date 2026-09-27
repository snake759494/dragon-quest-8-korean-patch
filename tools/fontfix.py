"""글꼴 확장 (SLPM_658.88): 한글 2,350자 + 자모를 대사(l3)·메뉴(s3) 글꼴 모두에.

1) 메뉴 글꼴 s3 를 l3 처럼 '4bpp 텍스처 3장 = 2bpp 페이지 6장(2,856칸)'으로:
   평면 선택(팔레트 교체)을 s3 에도 적용하고, 페이지 -> 텍스처 슬롯 계산을 slot = page/2 + 3 으로.
2) 글자표: s3(0x441A80)·l3(0x442A80) 각 4KB 버퍼 -> l3 도 0x441A80 을 가리켜 8KB 한 표를 함께 쓴다
   (두 글꼴의 글자 집합·순서를 같게 만든다). 크기 검사 slti 4097 -> 8193.
분석 근거: 0x2ED970(글자 그리기, 평면 선택), 0x2EE190(페이지->슬롯), 0x2EFEE0(s3 좌표), 0x16C6E4(평면 팔레트),
          0x2EFD30(글자표 읽기), 0x2EF650(이진 탐색).
"""
import struct

S3_PLANAR = [
    (0x16C6E4, 0x2AA10003, 0x2AA10006),   # slti at,s5,3 -> 6 : s3 텍스처에도 평면 팔레트 2개
    (0x2EDA08, 0x1460001B, 0x00000000),   # bne v1,zero(+172 s3) -> nop : s3 에도 평면 선택
    (0x2EE268, 0x28620003, 0x28620006),   # s3 페이지 6장 허용
    (0x2EE27C, 0x24640003, 0x00032043),   # addiu a0,v1,3 -> sra a0,v1,1   (slot = page/2 ...)
    (0x2EE288, 0x10000022, 0x10000021),   # 0x2EE310 의 daddu a1,zero,zero 를 거치게
    (0x2EE28C, 0x0000282D, 0x24840003),   # ... + 3
    (0x2EFF5C, 0x29440003, 0x29440006),   # s3 좌표 계산 페이지 6장 허용
]
L_TABLE_ADDIU = [0x2EBE88, 0x2EC010, 0x2EC064, 0x2EC150, 0x2EC1A4, 0x2EC630, 0x2EC764, 0x2EC7B8, 0x2EC8A4,
                 0x2EC8F8, 0x2EDB94, 0x2EE110, 0x2EF6B8, 0x2EF708, 0x2EFB68, 0x2EFC34, 0x2EFC84, 0x2EFDFC,
                 0x2EFE6C]
SIZE_CHECK = [0x2EFDD8, 0x2EFE0C, 0x2EFE44, 0x2EFE7C]
TABLE_MAX = (8192 - 8) // 2


def _o(va):
    return va - 0x100000 + 0x180


def patch(elf):
    for va, old, new in S3_PLANAR:
        assert struct.unpack_from('<I', elf, _o(va))[0] == old, hex(va)
        struct.pack_into('<I', elf, _o(va), new)
    for va in L_TABLE_ADDIU:                               # addiu rt,rs,0x2A80 -> 0x1A80
        w = struct.unpack_from('<I', elf, _o(va))[0]
        assert w >> 26 == 9 and w & 0xffff == 0x2A80, (hex(va), hex(w))
        struct.pack_into('<I', elf, _o(va), (w & 0xffff0000) | 0x1A80)
    for va in SIZE_CHECK:
        assert struct.unpack_from('<I', elf, _o(va))[0] == 0x28411001, hex(va)
        struct.pack_into('<I', elf, _o(va), 0x28412001)
