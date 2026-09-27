"""File formats: chunk pak (.pak/.pac), .mes (u16 font-table codes), .str (SJIS id table), event .txt (SJIS)."""
import struct

# ---------------------------------------------------------------- pak
# entry: 0x50-byte header (name / path strings in the first 0x40 bytes, then u32 header_size=0x50,
# u32 data_size, u32 total_size (to next entry, 16-aligned), u32 ?) followed by data.
# terminated by a header whose sizes are 0xffffffff.


class Pak:
    def __init__(self, data):
        self.items = []  # [header(0x50 bytes), data]
        p = 0
        while p + 0x50 <= len(data):
            hs, ds, tot, _ = struct.unpack_from('<IIII', data, p + 0x40)
            if hs != 0x50 or ds == 0xffffffff:
                break
            self.items.append([bytearray(data[p:p + 0x50]), bytes(data[p + hs:p + hs + ds])])
            p += tot
        self.tail = bytes(data[p:])  # terminator header + padding

    def names(self):
        return [h[:0x20].split(b'\0')[0].decode('ascii', 'replace') for h, _ in self.items]

    def get(self, name):
        for (h, d), n in zip(self.items, self.names()):
            if n == name:
                return d
        raise KeyError(name)

    def put(self, name, data):
        for it, n in zip(self.items, self.names()):
            if n == name:
                it[1] = bytes(data)
                return
        raise KeyError(name)

    def build(self):
        out = bytearray()
        for h, d in self.items:
            tot = (0x50 + len(d) + 15) & ~15
            h = bytearray(h)
            struct.pack_into('<II', h, 0x44, len(d), tot)
            out += h + d + b'\0' * (tot - 0x50 - len(d))
        return bytes(out + self.tail)


# ---------------------------------------------------------------- mes
# u16 count, u16 end, count * (u16 id, u16 ofs).  Message starts at byte 2*(ofs+count+1).
# Text area = END, then per message: NL, codes..., END.  `end` = byte size of the used data.
# codes < 0xf000 = index into the font table (l3 or s3); 0xff00 = newline, 0xff01 = end,
# other >= 0xf000 = control codes.
NL, END = 0xff00, 0xff01


class Mes:
    """layout-preserving .mes: every message keeps its original terminator tail"""

    def __init__(self, b):
        self.raw_len = len(b)
        cnt, end = struct.unpack_from('<HH', b)
        while end + 0x10000 <= len(b):      # u16 field wraps for files > 64 KB
            end += 0x10000
        self.end = end
        self.ids = [struct.unpack_from('<HH', b, 4 + 4 * i) for i in range(cnt)]
        area = 4 + 4 * cnt
        words = list(struct.unpack_from('<%dH' % ((self.end - area) // 2), b, area))
        starts = sorted(set((2 * (off + cnt + 1) - area) // 2 for _, off in self.ids))
        self.prefix = words[:starts[0]] if starts else words
        self.chunks = {}      # start -> [codes, tail]
        for k, s in enumerate(starts):
            e = starts[k + 1] if k + 1 < len(starts) else len(words)
            ch = words[s:e]
            n = ch.index(END) if END in ch else len(ch)
            self.chunks[s] = [ch[:n], ch[n:]]
        self.start_of = {mid: (2 * (off + cnt + 1) - area) // 2 for mid, off in self.ids}
        self.pad16 = len(b) % 16 == 0

    def messages(self):
        return [(mid, self.chunks[self.start_of[mid]][0]) for mid, _ in self.ids]

    def set(self, mid, codes):
        self.chunks[self.start_of[mid]][0] = list(codes)

    def build(self):
        cnt = len(self.ids)
        area = 4 + 4 * cnt
        words = list(self.prefix)
        newpos = {}
        for s in sorted(self.chunks):
            newpos[s] = len(words)
            codes, tail = self.chunks[s]
            words += codes + tail
        out = bytearray(struct.pack('<HH', cnt, 0))
        for mid, _ in self.ids:
            byte = area + 2 * newpos[self.start_of[mid]]
            ofs = byte // 2 - cnt - 1
            assert 0 <= ofs < 0x10000, 'mes too large'
            out += struct.pack('<HH', mid, ofs)
        out += struct.pack('<%dH' % len(words), *words)
        assert len(out) < 0x20000, 'mes too large (%d)' % len(out)
        struct.pack_into('<H', out, 2, len(out) & 0xffff)
        if self.pad16:
            out += b'\0' * (-len(out) % 16)
        return bytes(out)


# ---------------------------------------------------------------- str (cmdstr.str etc.)
# u32 count, 12 bytes 0, count * (u32 id, u32 ofs), NUL-terminated SJIS strings


def str_parse(b):
    cnt = struct.unpack_from('<I', b)[0]
    ents = [struct.unpack_from('<II', b, 0x10 + 8 * i) for i in range(cnt)]
    out = []
    for mid, off in ents:
        e = b.index(b'\0', off)
        out.append((mid, b[off:e]))
    return out


def str_build(items, head=None):
    cnt = len(items)
    out = bytearray(struct.pack('<I', cnt) + (head or b'\0' * 12))
    pos = 0x10 + 8 * cnt
    body = bytearray()
    for mid, s in items:
        out += struct.pack('<II', mid, pos + len(body))
        body += s + b'\0'
    return bytes(out + body)


# ---------------------------------------------------------------- event .txt
# "@ID\r\n" + lines + "\r\n" (blank line) ... "@9999999\r\n\r\n" + space padding to 16


def evtxt_parse(b, nl=b'\r\n'):
    lines = b.rstrip(b' \0').split(nl)
    blocks = []
    for ln in lines:
        if ln[:1] == b'@' and ln[1:].isdigit():
            blocks.append([ln[1:].decode('ascii'), []])
        elif blocks:
            blocks[-1][1].append(ln)
    out = []
    for head, body in blocks:
        while body and body[-1] == b'':
            body.pop()
        out.append((head, nl.join(body)))
    return out


def evtxt_build(blocks, nl=b'\r\n'):
    out = bytearray()
    for k, (head, body) in enumerate(blocks):
        out += b'@' + head.encode('ascii') + nl
        if k == len(blocks) - 1 and not body:
            out += nl                       # terminator block (@9999999)
        else:
            out += body + nl + nl
    out += b'\0' * (-len(out) % 16)
    return bytes(out)
