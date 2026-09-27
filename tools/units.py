"""남은 번역 파일을 작업 단위로 묶는다 -> translation/units.json"""
import os, glob, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR = os.path.join(ROOT, 'translation')
SKIP = ('elf/', 'str/', 'btl/', 'mes/menu', 'mes/title', 'mes/meswin')
LIMIT, BIG = 60000, 70000


def main():
    todo = []
    for f in glob.glob(os.path.join(TR, 'jp', '**', '*.tsv'), recursive=True):
        rel = os.path.relpath(f, os.path.join(TR, 'jp')).replace(os.sep, '/')
        if rel.startswith(SKIP):
            continue
        base = os.path.join(TR, 'ko', rel)
        if os.path.exists(base) or os.path.exists(base[:-4] + '.part1.tsv'):
            continue
        n = sum(len(l) for l in open(f, encoding='utf-8') if 'DUMMY' not in l)
        todo.append((rel, n))
    todo.sort()
    units, cur, sz = [], [], 0
    for rel, n in todo:
        if n > BIG:
            units.append([rel])
            continue
        if sz + n > LIMIT and cur:
            units.append(cur)
            cur, sz = [], 0
        cur.append(rel)
        sz += n
    if cur:
        units.append(cur)
    json.dump(units, open(os.path.join(TR, 'units.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(len(todo), 'files', sum(n for _, n in todo), 'chars', len(units), 'units')
    print('big', [(r, n) for r, n in todo if n > BIG])


if __name__ == '__main__':
    main()
