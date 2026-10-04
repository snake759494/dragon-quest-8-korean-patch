"""MPEG-2 GOP 제자리 재인코딩: 같은 장수·같은 크기 이하로 만들어 ES 의 그 GOP 자리에 넣는다(남는 자리는 0 채움)."""
import re, subprocess
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 512, 448


def gops(es):
    """[(시작, 끝, 사진 수)] — GOP 헤더(또는 첫 시퀀스 헤더)부터 다음 GOP 까지"""
    starts, pics = [], []
    for m in re.finditer(b'\x00\x00\x01([\x00\xb8])', es):
        if m.group(1) == b'\xb8':
            starts.append(m.start()); pics.append(0)
        elif pics:
            pics[-1] += 1
    return [(s, starts[i + 1] if i + 1 < len(starts) else len(es), pics[i]) for i, s in enumerate(starts)]


def decode(es, out_frames=None):
    """ES 전체를 디코딩해 프레임(rgb24 bytes)을 차례로 내보낸다"""
    p = subprocess.Popen([FF, '-loglevel', 'error', '-f', 'mpegvideo', '-i', '-', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    import threading
    threading.Thread(target=lambda: (p.stdin.write(es), p.stdin.close()), daemon=True).start()
    while True:
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            break
        yield b


def encode_gop(frames, limit, fps='30'):
    """frames(rgb24 bytes 목록)를 닫힌 GOP 하나로. limit 바이트 이하가 되는 가장 좋은 화질"""
    raw = b''.join(frames)
    for q in (2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 17, 20, 24, 31):
        r = subprocess.run([FF, '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', fps,
                            '-i', '-', '-c:v', 'mpeg2video', '-q:v', str(q), '-g', str(len(frames)), '-bf', '2',
                            '-flags', '+cgop', '-sc_threshold', '1000000000', '-b_strategy', '0',
                            '-pix_fmt', 'yuv420p', '-f', 'mpeg2video', '-'], input=raw, capture_output=True)
        out = r.stdout
        g = out.find(b'\x00\x00\x01\xb8')
        body = out[g:]
        if body.endswith(b'\x00\x00\x01\xb7'):
            body = body[:-4]
        assert body.count(b'\x00\x00\x01\xb8') == 1, 'GOP 가 둘 이상'
        n = len(re.findall(b'\x00\x00\x01\x00', body))
        assert n == len(frames), (n, len(frames))
        if len(body) <= limit:
            return body, q
    raise ValueError('크기 맞추기 실패')
