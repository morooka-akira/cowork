#!/usr/bin/env python3
"""
PPTX テンプレート変換スクリプト

元のPPTXのレイアウトを保持したまま、テキスト内容だけを差し替えて
新しいプレゼンテーションを生成する。

使い方:
  1. mapping.json に変換ルールを書く（後述）
  2. python convert_pptx.py template.pptx mapping.json output.pptx

mapping.json の構造:
{
  "keep_slides": [1, 2, 3, 10, 12],     // 残すスライド番号（1始まり）
  "replacements": {                       // テキスト置換マッピング
    "TagOne開発プロジェクトMTG": "家のリフォームプロジェクトMTG",
    "タイムラボアジェンダ": "施主側アジェンダ",
    ...
  }
}

変換ロジック:
  Step 1: テンプレートPPTXをZIP展開 → XMLをpretty print
  Step 2: presentation.xml の <p:sldIdLst> から不要スライドのIDを削除
  Step 3: 残ったスライドのXML内 <a:t> タグのテキストを置換
  Step 4: 孤立ファイル（削除スライド・未使用メディア）を掃除
  Step 5: ZIP再パッケージして .pptx として出力

依存:
  pip install defusedxml
"""

import argparse
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

try:
    from defusedxml import minidom
except ImportError:
    from xml.dom import minidom
    print("WARNING: defusedxml not found, using stdlib minidom", file=sys.stderr)


# ─────────────────────────────────────────────
# Step 1: Unpack
# ─────────────────────────────────────────────
def unpack(pptx_path: str, dest_dir: str) -> None:
    """PPTXを展開し、XMLファイルをpretty printする"""
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir)

    with zipfile.ZipFile(pptx_path, "r") as zf:
        zf.extractall(dest_dir)

    # XMLをpretty print（読みやすく＋Edit toolで編集しやすく）
    for root, _, files in os.walk(dest_dir):
        for fname in files:
            if fname.endswith(".xml") or fname.endswith(".rels"):
                fpath = os.path.join(root, fname)
                try:
                    doc = minidom.parse(fpath)
                    pretty = doc.toprettyxml(indent="  ", encoding="utf-8")
                    # minidomが追加する余分な空行を除去
                    lines = pretty.decode("utf-8").split("\n")
                    lines = [l for l in lines if l.strip()]
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write("\n".join(lines) + "\n")
                except Exception:
                    pass  # バイナリ混在ファイルなどはスキップ


# ─────────────────────────────────────────────
# Step 2: スライド選択（不要スライドを削除）
# ─────────────────────────────────────────────
def select_slides(unpacked_dir: str, keep_slides: list[int]) -> None:
    """
    presentation.xml の <p:sldIdLst> を編集して
    keep_slides に含まれないスライドを削除する。

    keep_slides: 残すスライドの番号リスト（1始まり）。
                 順番はこのリストの順に並び替えられる。
    """
    pres_path = os.path.join(unpacked_dir, "ppt", "presentation.xml")
    with open(pres_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 既存の sldId エントリをすべて抽出
    pattern = r'<p:sldId\s+id="(\d+)"\s+r:id="(rId\d+)"\s*/>'
    entries = re.findall(pattern, content)  # [(id, rId), ...]

    if not entries:
        print("ERROR: <p:sldIdLst> にスライドが見つかりません", file=sys.stderr)
        sys.exit(1)

    print(f"  元のスライド数: {len(entries)}")

    # スライド番号（1始まり）→ エントリのインデックス（0始まり）
    # rId7 が slide1, rId8 が slide2, ... という前提（Googleスライド標準）
    # ただし実際のマッピングは .rels ファイルで確認すべき

    # presentation.xml.rels からスライド番号とrIdのマッピングを取得
    rels_path = os.path.join(unpacked_dir, "ppt", "_rels", "presentation.xml.rels")
    with open(rels_path, "r", encoding="utf-8") as f:
        rels_content = f.read()

    # rId → slideN のマッピング
    rid_to_slide = {}
    for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="slides/slide(\d+)\.xml"', rels_content):
        rid_to_slide[m.group(1)] = int(m.group(2))

    # slideN → (id, rId) のマッピング
    slide_to_entry = {}
    for sid, rid in entries:
        slide_num = rid_to_slide.get(rid)
        if slide_num is not None:
            slide_to_entry[slide_num] = (sid, rid)

    # keep_slides の順番で新しい sldIdLst を構築
    new_entries = []
    for sn in keep_slides:
        if sn in slide_to_entry:
            new_entries.append(slide_to_entry[sn])
        else:
            print(f"  WARNING: slide{sn} が見つかりません、スキップ", file=sys.stderr)

    # 新しい sldIdLst XML を生成
    new_lines = ['  <p:sldIdLst>']
    for sid, rid in new_entries:
        new_lines.append(f'    <p:sldId id="{sid}" r:id="{rid}"/>')
    new_lines.append('  </p:sldIdLst>')
    new_sld_list = "\n".join(new_lines)

    # 既存の sldIdLst を置換
    content = re.sub(
        r'<p:sldIdLst>.*?</p:sldIdLst>',
        new_sld_list,
        content,
        flags=re.DOTALL,
    )

    with open(pres_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  残したスライド: {keep_slides} ({len(new_entries)}枚)")


# ─────────────────────────────────────────────
# Step 3: テキスト置換
# ─────────────────────────────────────────────
def replace_texts(unpacked_dir: str, replacements: dict[str, str]) -> None:
    """
    残ったスライドXML内の <a:t>テキスト</a:t> を置換する。

    置換対象は ppt/slides/slide*.xml のみ。
    レイアウト（位置、サイズ、フォント、色、行間など）には一切触れない。
    """
    slides_dir = os.path.join(unpacked_dir, "ppt", "slides")
    if not os.path.exists(slides_dir):
        print("ERROR: ppt/slides/ ディレクトリが見つかりません", file=sys.stderr)
        sys.exit(1)

    count = 0
    for fname in sorted(os.listdir(slides_dir)):
        if not fname.startswith("slide") or not fname.endswith(".xml"):
            continue
        fpath = os.path.join(slides_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        original = content
        for old_text, new_text in replacements.items():
            content = content.replace(old_text, new_text)

        if content != original:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            count += 1

    print(f"  テキスト置換: {len(replacements)}パターン → {count}ファイル更新")


# ─────────────────────────────────────────────
# Step 4: 孤立ファイル掃除
# ─────────────────────────────────────────────
def clean_orphans(unpacked_dir: str) -> None:
    """
    presentation.xml の sldIdLst に含まれないスライドと
    それに紐づくメディア・ノート・relsファイルを削除する。
    """
    pres_path = os.path.join(unpacked_dir, "ppt", "presentation.xml")
    with open(pres_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 残っている rId を取得
    kept_rids = set(re.findall(r'r:id="(rId\d+)"', content))

    # presentation.xml.rels から全スライドのrId→ファイルマッピング
    rels_path = os.path.join(unpacked_dir, "ppt", "_rels", "presentation.xml.rels")
    with open(rels_path, "r", encoding="utf-8") as f:
        rels_content = f.read()

    removed = 0
    for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="slides/(slide\d+\.xml)"', rels_content):
        rid, slide_file = m.group(1), m.group(2)
        if rid not in kept_rids:
            # スライド本体
            slide_path = os.path.join(unpacked_dir, "ppt", "slides", slide_file)
            if os.path.exists(slide_path):
                os.remove(slide_path)
                removed += 1

            # スライドのrels
            rels_file = os.path.join(
                unpacked_dir, "ppt", "slides", "_rels", slide_file + ".rels"
            )
            if os.path.exists(rels_file):
                # relsの中身からnotes等の参照先も削除
                with open(rels_file, "r", encoding="utf-8") as f:
                    rel_content = f.read()
                for note_m in re.finditer(r'Target="../notesSlides/(notesSlide\d+\.xml)"', rel_content):
                    note_file = note_m.group(1)
                    note_path = os.path.join(unpacked_dir, "ppt", "notesSlides", note_file)
                    if os.path.exists(note_path):
                        os.remove(note_path)
                    note_rels = os.path.join(
                        unpacked_dir, "ppt", "notesSlides", "_rels", note_file + ".rels"
                    )
                    if os.path.exists(note_rels):
                        os.remove(note_rels)

                os.remove(rels_file)

    # Content_Types.xml からも削除されたスライドへの参照を除去
    ct_path = os.path.join(unpacked_dir, "[Content_Types].xml")
    if os.path.exists(ct_path):
        with open(ct_path, "r", encoding="utf-8") as f:
            ct = f.read()
        # 存在しないスライドファイルへの Override を削除
        slides_dir = os.path.join(unpacked_dir, "ppt", "slides")
        existing_slides = set(os.listdir(slides_dir)) if os.path.exists(slides_dir) else set()

        def keep_override(m):
            part = m.group(0)
            # /ppt/slides/slideN.xml へのOverrideで、ファイルが存在しなければ削除
            slide_match = re.search(r'/ppt/slides/(slide\d+\.xml)', part)
            if slide_match and slide_match.group(1) not in existing_slides:
                return ""
            note_match = re.search(r'/ppt/notesSlides/(notesSlide\d+\.xml)', part)
            if note_match:
                note_path = os.path.join(unpacked_dir, "ppt", "notesSlides", note_match.group(1))
                if not os.path.exists(note_path):
                    return ""
            return part

        ct = re.sub(r'<Override[^>]*/>', keep_override, ct)
        with open(ct_path, "w", encoding="utf-8") as f:
            f.write(ct)

    print(f"  孤立ファイル削除: {removed}スライド分")


# ─────────────────────────────────────────────
# Step 5: 再パッケージ
# ─────────────────────────────────────────────
def pack(unpacked_dir: str, output_path: str) -> None:
    """展開ディレクトリを .pptx として再ZIP化する"""
    # [Content_Types].xml は先頭に来る必要がある
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        ct_path = os.path.join(unpacked_dir, "[Content_Types].xml")
        if os.path.exists(ct_path):
            zf.write(ct_path, "[Content_Types].xml")

        for root, _, files in os.walk(unpacked_dir):
            for fname in sorted(files):
                fpath = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, unpacked_dir)
                if arcname == "[Content_Types].xml":
                    continue  # 既に追加済み
                zf.write(fpath, arcname)

    print(f"  出力: {output_path}")


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="PPTXテンプレートのレイアウトを保持してテキストだけ差し替える"
    )
    parser.add_argument("template", help="元のPPTXファイル")
    parser.add_argument("mapping", help="変換ルールJSON (mapping.json)")
    parser.add_argument("output", help="出力PPTXファイル")
    parser.add_argument(
        "--work-dir", default="_work_unpacked",
        help="作業用一時ディレクトリ (デフォルト: _work_unpacked)"
    )
    args = parser.parse_args()

    # mapping.json 読み込み
    with open(args.mapping, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    keep_slides = mapping.get("keep_slides", [])
    replacements = mapping.get("replacements", {})

    if not keep_slides:
        print("ERROR: keep_slides が空です", file=sys.stderr)
        sys.exit(1)

    print(f"=== PPTX変換開始 ===")
    print(f"  テンプレート: {args.template}")
    print(f"  マッピング:   {args.mapping}")
    print()

    # Step 1
    print("[Step 1] Unpack...")
    unpack(args.template, args.work_dir)

    # Step 2
    print("[Step 2] スライド選択...")
    select_slides(args.work_dir, keep_slides)

    # Step 3
    print("[Step 3] テキスト置換...")
    replace_texts(args.work_dir, replacements)

    # Step 4
    print("[Step 4] 孤立ファイル掃除...")
    clean_orphans(args.work_dir)

    # Step 5
    print("[Step 5] パッケージング...")
    pack(args.work_dir, args.output)

    # 作業ディレクトリ削除
    shutil.rmtree(args.work_dir)

    print()
    print(f"=== 完了: {args.output} ===")


if __name__ == "__main__":
    main()
