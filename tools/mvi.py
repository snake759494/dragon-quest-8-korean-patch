"""동영상(MOVIE/*.MVI) 형식: PSS(MPEG-2 PS)를 0x4000바이트 키로 XOR 한 것.

- 0x4000 청크 = 팩 헤더(14) + PES 4개(0x100E 간격, 첫 셋은 0x1000, 마지막은 0xFF2 바이트).
- PES 스트림 번호 바이트(o+3)가 키와 같으면(= 평문 E0) 비디오, 아니면 오디오. 비디오 ES 는 o+19 부터.
- 첫 청크는 형식이 달라(파일 머리) 시퀀스 헤더만 떼어 쓴다(자막 구간은 첫 청크에 없다).
- 키(tools/mvi_key.npy)는 전체 동영상의 바이트 통계(평문 최빈값 0)로 구했다.
"""
import os
import numpy as np

B = 0x4000
K = np.load(os.path.join(os.path.dirname(__file__), 'mvi_key.npy'))


class Movie:
    def __init__(self, data):
        d = np.frombuffer(data, np.uint8)
        self.n = len(d) // B
        self.tail = bytes(data[self.n * B:])
        self.c = d[:self.n * B].reshape(self.n, B).copy()
        p = self.c ^ K
        c0 = p[0].tobytes()
        s = c0.find(b'\0\0\1\xb3')
        e = c0.find(b'\0\0\1\x00', s)
        es = [c0[s:e]]
        self.head = len(es[0])                 # ES 앞머리(시퀀스 헤더, 원본 위치로 되돌리지 않음)
        self.map = []                           # (es 위치, 청크, 청크 안 위치, 길이)
        pos = self.head
        for k in range(1, self.n):
            for q in range(4):
                o = 14 + 0x1000 * q
                if self.c[k, o + 3] != K[o + 3]:
                    continue
                a, b = o + 19, min(o + 0x1000, B)
                es.append(p[k, a:b].tobytes())
                self.map.append((pos, k, a, b - a))
                pos += b - a
        self.es = b''.join(es)

    def build(self, es):
        assert len(es) == len(self.es)
        c = self.c.copy()
        buf = np.frombuffer(es, np.uint8)
        for pos, k, a, ln in self.map:
            c[k, a:a + ln] = buf[pos:pos + ln] ^ K[a:a + ln]
        return c.tobytes() + self.tail
