"""Patch DATA.DAT files into a copy of the Japanese ISO.

A replaced file is written over its original slot when it fits (slot = up to the next file),
otherwise appended after the end of DATA.DAT, growing DATA.DAT into the DMYDATA padding file
(DMYDATA is dummy filler; its extent is shifted forward).  DATA.HD6 is rewritten each build
from the original index, so unchanged entries always point at original data.  Slots overwritten in
a previous build but no longer patched are restored from the original ISO (build/manifest.json).
"""
import os, json, shutil, struct
import dq8arc
from dq8arc import SECTOR, DAT_LBA, DAT_SIZE, DMY_LBA, DMY_SIZE, HD6_LBA, HD6_SIZE

ROOT = dq8arc.ROOT
MANIFEST = os.path.join(ROOT, 'build', 'manifest.json')


def _root_records(f):
    f.seek(16 * SECTOR)
    pvd = f.read(SECTOR)
    assert pvd[1:6] == b'CD001'
    root = pvd[156:156 + 34]
    lba, size = struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0]
    f.seek(lba * SECTOR)
    data = f.read(size)
    recs, o = {}, 0
    while o < len(data):
        n = data[o]
        if n == 0:
            o = (o // SECTOR + 1) * SECTOR
            continue
        name = data[o + 33:o + 33 + data[o + 32]].decode('ascii', 'replace').split(';')[0]
        recs[name] = lba * SECTOR + o
        o += n
    return recs


def _set_record(f, recoff, lba, size):
    f.seek(recoff + 2)
    f.write(struct.pack('<I', lba) + struct.pack('>I', lba) + struct.pack('<I', size) + struct.pack('>I', size))


def patch_iso_files(out_iso, isofiles):
    """ISO 안 일반 파일(SLPM_658.88, BIN/*.BIN)을 같은 크기로 제자리에 덮어쓴다"""
    import pycdlib
    iso = pycdlib.PyCdlib()
    iso.open(dq8arc.ISO_JP)
    locs = {}
    for path in isofiles:
        r = iso.get_record(iso_path='/' + path + ';1')
        locs[path] = (r.extent_location(), r.get_data_length())
    iso.close()
    with open(out_iso, 'r+b') as f:
        recs = _root_records(f)
        for path, data in isofiles.items():
            lba, size = locs[path]
            cap = (size + SECTOR - 1) // SECTOR * SECTOR
            assert size <= len(data) <= cap, (path, len(data), cap)      # 마지막 섹터 여유까지만
            f.seek(lba * SECTOR)
            f.write(data)
            name = path.split('/')[-1]
            if name in recs:                                          # 루트의 파일은 크기 값 갱신
                _set_record(f, recs[name], lba, len(data))


def patch(out_iso, files, log=print, isofiles=None):
    """files: {archive name: bytes}"""
    src = dq8arc.arc()
    if not os.path.exists(out_iso):
        log('copying original ISO ...')
        shutil.copyfile(dq8arc.ISO_JP, out_iso)
    hd6 = dq8arc.HD6(src.hd6.d)            # fresh copy of the original index
    old = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {}
    f = open(out_iso, 'r+b')
    dat0 = DAT_LBA * SECTOR

    # restore slots patched last time but not now (or that will be rewritten anyway)
    for name, (ofs, size) in old.items():
        e = hd6.get(name)
        if name not in files and ofs == e.ofs:
            f.seek(dat0 + e.ofs)
            f.write(src.read(e))

    append = DAT_SIZE
    manifest = {}
    for name, data in sorted(files.items()):
        e = hd6.get(name)
        cap = hd6.slot_end(e) - e.ofs
        if len(data) <= cap:
            ofs = e.ofs
        else:
            ofs = (append + 0x7ff) & ~0x7ff
            append = ofs + len(data)
        f.seek(dat0 + ofs)
        f.write(data + b'\0' * (-len(data) % 16))
        hd6.set(e, ofs, len(data))
        manifest[name] = (ofs, len(data))

    new_size = max(DAT_SIZE, (append + 15) & ~15)
    dat_sectors = (new_size + SECTOR - 1) // SECTOR
    assert DAT_LBA + dat_sectors < DMY_LBA + DMY_SIZE // SECTOR, 'DMYDATA area exhausted'
    recs = _root_records(f)
    _set_record(f, recs['DATA.DAT'], DAT_LBA, new_size)
    new_dmy = DAT_LBA + dat_sectors
    dmy_end = DMY_LBA * SECTOR + DMY_SIZE
    _set_record(f, recs['DMYDATA.'] if 'DMYDATA.' in recs else recs['DMYDATA'], new_dmy, dmy_end - new_dmy * SECTOR)

    assert len(hd6.d) == HD6_SIZE
    f.seek(HD6_LBA * SECTOR)
    f.write(hd6.d)
    f.close()
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    json.dump(manifest, open(MANIFEST, 'w'), indent=0)
    if isofiles:
        patch_iso_files(out_iso, isofiles)
    log('patched %d files, DATA.DAT +%d bytes appended' % (len(files), new_size - DAT_SIZE))
