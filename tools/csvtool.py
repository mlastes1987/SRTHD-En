#!/usr/bin/env python3
"""CSV import/export for the SRW HD translation kit."""
import csv
import json
import sys


def to_csv(json_in, csv_out):
    ents = json.load(open(json_in, encoding="utf-8"))
    ents.sort(key=lambda e: (e.get("bank") is None, e.get("bank") or 0,
                             e.get("index") or 0, e["off"]))
    with open(csv_out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "bank", "index", "offset", "enc", "japanese", "english"])
        for e in ents:
            w.writerow([e["id"],
                        "%08x" % e["bank"] if e.get("bank") is not None else "",
                        "" if e.get("index") is None else e["index"],
                        "%08x" % e["off"], e["enc"],
                        e["text"], e.get("translation", "")])
    print("wrote %d rows -> %s" % (len(ents), csv_out))


def from_csv(json_base, csv_in, json_out):
    ents = json.load(open(json_base, encoding="utf-8"))
    by_id = {e["id"]: e for e in ents}
    n = 0
    with open(csv_in, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            e = by_id.get(int(row["id"]))
            if not e:
                continue
            text = row.get("english") or ""
            if text and text != e["text"]:
                e["translation"] = text
                n += 1
    json.dump(ents, open(json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("applied %d translations -> %s" % (n, json_out))


if __name__ == "__main__":
    if sys.argv[1] == "export":
        to_csv(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "apply":
        from_csv(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__)
