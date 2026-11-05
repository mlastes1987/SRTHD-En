"""Pixel-aware battle quote wrapping; preserves every translated word.

The quote table covers UTF-8 strings 0x422410..0x46f350, including rows
whose nominal bank was lost by the original extractor's false references.
Battle balloons have two visible lines. Longer quotes are paged at runtime
by battle_pages.py, without introducing control codes into other consumers.
"""
import argparse
import csv
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / 'work/text/translation.csv'
WIDTH = 800
SIZE = 38


def flatten(text):
    return re.sub(r'\s+', ' ', text).strip()


def measure(text, metrics):
    return sum(int(metrics[c]['advance'] * SIZE + metrics[c]['adjust_px'])
               if c in metrics else SIZE for c in text)


def wrap(text, metrics):
    words = flatten(text).split(' ')
    lines, current = [], ''
    for word in words:
        candidate = (current + ' ' + word).strip()
        # Leave a full glyph for the opening quote / continuation indent.
        if current and measure(candidate, metrics) > WIDTH - SIZE:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return '\n\u3000'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    metrics = json.loads((ROOT / 'work/text/proportional_metrics.json').read_text())['metrics']
    with CSV.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    report = []
    for row in rows:
        if not 0x422410 <= int(row['offset'], 16) < 0x46f350:
            continue
        before = row['english']
        after = wrap(before, metrics)
        assert flatten(before) == flatten(after)
        assert all(measure(line, metrics) + (SIZE if i == 0 else 0) <= WIDTH
                   for i, line in enumerate(after.splitlines()))
        # The native quote builder adds UTF-8 quotation marks. Its 121-byte
        # buffer reserves bytes 104..106 for our page offset and timer.
        assert len(after.encode('utf-8')) + 7 <= 104, row['id']
        assert len(after.splitlines()) <= 4, row['id']
        report.append(dict(id=int(row['id']), offset=row['offset'],
                           before=before, after=after,
                           lines=len(after.splitlines()),
                           pages=(len(after.splitlines()) + 1)//2))
        row['english'] = after
    if args.apply:
        backup = CSV.with_name('translation.csv.before_battle_pages_2026-11-04')
        if not backup.exists():
            shutil.copy2(CSV, backup)
        with CSV.open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    (ROOT / 'work/text/battle_dialogue_report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Scanned {len(report)} quotes; {sum(r['before'] != r['after'] for r in report)} rewrapped; "
          f"{sum(r['pages'] > 1 for r in report)} require two pages. All words retained.")
    print(next(r for r in report if r['id'] == 3739))


if __name__ == '__main__':
    main()
