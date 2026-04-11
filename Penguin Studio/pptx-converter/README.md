# PPTX テンプレート変換ツール

PPTXのレイアウト（色・フォント・位置・行間・背景）を一切変えずに、テキスト内容だけを差し替えて新しいプレゼンを生成する。

## 使い方

```bash
python convert_pptx.py <テンプレート.pptx> <mapping.json> <出力.pptx>
```

### 実行例

```bash
python convert_pptx.py \
  "[分科会]TagOne開発プロジェクトMTGアジェンダ.pptx" \
  mapping_example.json \
  "家のリフォームプロジェクトMTG.pptx"
```

## mapping.json の書き方

```json
{
  "keep_slides": [1, 2, 3, 10],
  "replacements": {
    "元のテキスト": "新しいテキスト",
    "TagOne": "リフォーム"
  }
}
```

| キー | 説明 |
|------|------|
| `keep_slides` | 残すスライド番号（1始まり）。この順番で並ぶ |
| `replacements` | `{元テキスト: 新テキスト}` の辞書。完全一致で置換 |

### スライド番号の調べ方

```bash
pip install "markitdown[pptx]"
python -m markitdown template.pptx
```

`<!-- Slide number: N -->` で各スライドの番号と内容がわかる。

## 変換ロジック（5ステップ）

```
テンプレート.pptx
    │
    ▼ Step 1: ZIP展開 + XML整形
  _work_unpacked/
    │
    ▼ Step 2: presentation.xml の <p:sldIdLst> 編集
              keep_slides に無いスライドIDを削除
    │
    ▼ Step 3: slide*.xml 内の <a:t> テキスト置換
              <a:pPr>（段落書式）や <a:rPr>（文字書式）は触らない
    │
    ▼ Step 4: 孤立ファイル削除
              - 削除されたスライドの .xml / .rels
              - 紐づくノートスライド
              - Content_Types.xml の不要エントリ
    │
    ▼ Step 5: ZIP再パッケージ
  出力.pptx
```

## 依存

```bash
pip install defusedxml
```

## 制限事項

- テキスト置換は単純な文字列マッチ。XMLタグをまたぐ置換はできない
- 画像・チャート・図形の中身は置換対象外
- スライドマスター/レイアウトのテキスト（フッター等）は変更されない
- 元テンプレートでハイパーリンク付きテキストを置換すると、リンクは残る場合がある
