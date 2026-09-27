"""DQ8 (PS2 JP, SLPM-65888) archive: DATA.HD6 index + DATA.DAT data.

HD6 header (u32 after 'HD6\\0'):
  pool_ofs, pool_size, pool_count, 0, names_ofs, names_size, 0, 16, n_entries, entries_ofs, 0, total
String pool: NUL separated fragments.  Name record i (NUL terminated) = fragment indices,
  1 byte (<0x80) or 2 bytes ((b0 & 0x7f) | b1 << 7).  Record i belongs to entry i.
Entry (8 bytes): u16 name_ofs & 0xffff, u24 ofs_field, u24 size_field
  data offset = (ofs_field & ~1) * 0x200   (bit 0 is a flag, kept as is)
  size        = size_field * 16
"""
import os, struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISO_JP = os.path.join(ROOT, 'Dragon Quest VIII - Sora to Umi to Daichi to Norowareshi Himegimi (Japan, Asia).iso')
SECTOR = 2048
HD6_LBA, HD6_SIZE = 2059, 192412
DAT_LBA, DAT_SIZE = 990124, 1983684608
DMY_LBA, DMY_SIZE = 1958720, 51166209


class Entry:
    __slots__ = ('i', 'name', 'ofs', 'size', 'flag')

    def __init__(self, i, name, ofs, size, flag):
        self.i, self.name, self.ofs, self.size, self.flag = i, name, ofs, size, flag

    def __repr__(self):
        return f'<{self.i} {self.name} ofs={self.ofs:#x} size={self.size:#x}>'


class HD6:
    def __init__(self, data):
        self.d = bytearray(data)
        (self.pool_ofs, pool_size, npool, _, self.names_ofs, names_size, _, _,
         self.n, self.ent_ofs, _, _) = struct.unpack_from('<12I', self.d, 4)
        pool = bytes(self.d[self.pool_ofs:self.pool_ofs + pool_size]).split(b'\0')[:npool]
        nt = bytes(self.d[self.names_ofs:self.names_ofs + names_size])
        recs, p = [], 0
        while p < len(nt):
            q = nt.find(b'\0', p)
            q = len(nt) if q < 0 else q
            recs.append(nt[p:q])
            p = q + 1
        self.entries = []
        for i in range(self.n):
            e = self.d[self.ent_ofs + 8 * i:self.ent_ofs + 8 * i + 8]
            of = int.from_bytes(e[2:5], 'little')
            sz = int.from_bytes(e[5:8], 'little')
            name = self._decode(recs[i], pool)
            self.entries.append(Entry(i, name, (of & ~1) * 0x200, sz * 16, of & 1))
        self.by_name = {}
        for e in self.entries:
            self.by_name.setdefault(e.name.lower(), e)

    @staticmethod
    def _decode(r, pool):
        s, i = b'', 0
        while i < len(r):
            b = r[i]
            i += 1
            if b & 0x80:
                b = (b & 0x7f) | (r[i] << 7)
                i += 1
            s += pool[b]
        return s.decode('cp932', 'replace')

    def get(self, name):
        return self.by_name[name.lower().replace('/', '\\')]

    def set(self, e, ofs, size):
        assert ofs % 0x400 == 0, hex(ofs)
        size16 = (size + 15) // 16
        assert size16 < 1 << 24
        o = self.ent_ofs + 8 * e.i
        self.d[o + 2:o + 5] = ((ofs // 0x200) | e.flag).to_bytes(3, 'little')
        self.d[o + 5:o + 8] = size16.to_bytes(3, 'little')
        e.ofs, e.size = ofs, size16 * 16

    def slot_end(self, e):
        """first byte after e that belongs to another file (or end of the original DATA.DAT)"""
        nxt = [x.ofs for x in self.entries if x.ofs > e.ofs]
        return min(nxt) if nxt else DAT_SIZE


class JPArchive:
    """read-only access to the original game data straight from the Japanese ISO"""

    def __init__(self, iso=ISO_JP):
        self.f = open(iso, 'rb')
        self.f.seek(HD6_LBA * SECTOR)
        self.hd6 = HD6(self.f.read(HD6_SIZE))

    def read(self, name):
        e = self.hd6.get(name) if isinstance(name, str) else name
        self.f.seek(DAT_LBA * SECTOR + e.ofs)
        return self.f.read(e.size)

    def names(self):
        return [e.name for e in self.hd6.entries]


_arc = None


def arc():
    global _arc
    if _arc is None:
        _arc = JPArchive()
    return _arc


def read(name):
    return arc().read(name)
