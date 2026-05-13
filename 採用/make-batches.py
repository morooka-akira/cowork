#!/usr/bin/env python3
# make-batches.py — list-data.json をバッチJSONに分割する
# 使い方: python3 make-batches.py <list-data.json> <list-page-url> <output-dir>
# 例:     python3 make-batches.py ./tmp/list-data.json \
#             "https://www.notion.so/34faf136accb81e0995fd7fb52265c8e" \
#             ng-nextlist
# 出力:   ./tmp/<output-dir>/nb001.json, nb002.json, ...
# dedup:  ./imported-ids.txt が存在すれば既登録IDをスキップ

import json
import os
import sys

IDS_FILE = os.path.join(os.path.dirname(__file__), 'imported-ids.txt')
OUTPUT_BASE = os.path.join(os.path.dirname(__file__), 'tmp')
BATCH_SIZE = 10


def load_imported_ids():
    if not os.path.exists(IDS_FILE):
        return set()
    with open(IDS_FILE) as f:
        return set(line.strip() for line in f if line.strip())


def to_page(c, list_page_url):
    def u(v):
        return v if v else None

    return {
        "properties": {
            "名前": c.get("name", ""),
            "recruit-marker-id": c.get("recruitMarkerId", ""),
            "会社/役職": c.get("companyInfo") or "",
            "プロフィール": (c.get("description") or "")[:500],
            "X": u(c.get("twitterUrl")),
            "GitHub": u(c.get("githubUrl")),
            "リンク": u(c.get("youtrustUrl")),
            "Wantedly": u(c.get("wantedlyUrl")),
            "Google": None,
            "Facebook": u(c.get("facebookUrl")),
            "LinkedIn": u(c.get("linkedinUrl")),
            "ステータス": "アプローチ前",
            "リスト": json.dumps([list_page_url], ensure_ascii=False),
        },
        "content": "",
    }


def main():
    if len(sys.argv) < 4:
        print("使い方: python3 make-batches.py <list-data.json> <list-page-url> <output-dir>")
        sys.exit(1)

    list_data_path = sys.argv[1]
    list_page_url = sys.argv[2]
    output_dir_name = sys.argv[3]

    output_dir = os.path.join(OUTPUT_BASE, output_dir_name)
    os.makedirs(output_dir, exist_ok=True)

    with open(list_data_path, encoding="utf-8") as f:
        data = json.load(f)

    candidates = data.get("candidates", [])
    imported_ids = load_imported_ids()

    new_candidates = [c for c in candidates if c.get("recruitMarkerId") not in imported_ids]
    skipped = len(candidates) - len(new_candidates)

    batches = [new_candidates[i:i + BATCH_SIZE] for i in range(0, len(new_candidates), BATCH_SIZE)]

    for i, batch in enumerate(batches):
        out_path = os.path.join(output_dir, f"nb{i + 1:03d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump([to_page(c, list_page_url) for c in batch], f, ensure_ascii=False)

    print(f"総候補者: {len(candidates)}件")
    if skipped:
        print(f"スキップ (既登録): {skipped}件")
    print(f"新規: {len(new_candidates)}件 → {len(batches)}バッチ ({output_dir})")


if __name__ == "__main__":
    main()
