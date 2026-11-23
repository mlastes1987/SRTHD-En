"""Check intermission text against the playtest screens' native rows."""
import csv
import json
from pathlib import Path

HELP_ROWS = set(range(5136, 5144))
EFFECT_ROWS = {
    5148, 5150, 5151, 5153, 5155, 5157, 5159, 5161, 5163, 5165, 5167,
    5169, 5171, 5173, 5175, 5177, 5179, 5181, 5183, 5185, 5187, 5189,
    5190, 5192, 5193, 5195, 5196, 5197, 5199, 5201, 5203, 5204, 5206,
    5207, 5209, 5211, 5213, 5215, 5217, 5218, 5220, 5221, 5223, 5224,
    5226, 5227, 5229, 5230, 5232, 5234,
}


def verify_rows(csv_path):
    metrics = json.loads(Path(__file__).with_name("vita_font_metrics.json").read_text())
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as stream:
        rows = {int(row["id"]): row["english"] for row in csv.DictReader(stream)}
    for key in sorted(HELP_ROWS | EFFECT_ROWS):
        text = rows[key]
        # Haro's first confirmation row has more room than the item preview.
        limit = 1080 if key in HELP_ROWS else 520 if key == 5195 else 456
        width = sum(int(metrics[c]["advance"] * 38 + metrics[c]["adjust_px"])
                    if c in metrics else 38 for c in text)
        if not text or "\n" in text or "\r" in text or width > limit:
            raise ValueError(f"Intermission text {key} exceeds one {limit}px row: {text!r} ({width}px)")
    return len(HELP_ROWS), len(EFFECT_ROWS)
