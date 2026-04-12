# AivisSpeech 女性音声 PoC

対話台本（JSON）から、2人の女性キャラが交互に話すポッドキャスト音声（WAV）を生成する。

---

## 前提条件

| ツール | バージョン | 確認コマンド |
|--------|-----------|------------|
| AivisSpeech Desktop | 最新版 | アプリが起動していること |
| uv | 最新版 | `uv --version` |
| ffmpeg | 任意 | `ffmpeg -version`（MP3変換が不要なら不要） |

### AivisSpeech のインストール

1. https://aivis-project.com/ からデスクトップアプリをダウンロード
2. インストール後、アプリを起動する
3. 起動すると自動的にエンジンが `http://127.0.0.1:10101` で立ち上がる
4. ブラウザで `http://127.0.0.1:10101/docs` にアクセスすると API 仕様書（Swagger UI）が確認できる

### uv のインストール（未インストールの場合）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## セットアップ

```bash
cd strategy/poc/voice-poc

# .venv を作成して依存パッケージを同期
uv sync
```

`uv sync` は `pyproject.toml` と `uv.lock` を参照して `.venv/` に仮想環境を作る。
`pip install` は不要。Python 3.12 が自動的に使われる（`.python-version` に定義済み）。

---

## 実行手順

### Step 1 — スピーカー一覧を確認する

AivisSpeech を起動した状態で実行する。

```bash
uv run python list_speakers.py
```

出力例:

```
    ID  スピーカー名              スタイル名
--------------------------------------------------
888753760  Anneli                ノーマル
888753761  Anneli                テンション高め
123456789  四国めたん             ノーマル
...
```

- 左端の **ID** が `speaker_id` として使う数値
- 女性らしい声・キャラの差が出やすい2つのIDを選ぶ
- AivisHub（https://hub.aivis-project.com/）で試聴してから選ぶと確実

### Step 2 — `dialogue.json` にスピーカーIDを設定する

`dialogue.json` の `speaker_id` に Step 1 で確認した数値を書き込む。

```json
"speakers": {
  "あかり": {
    "speaker_id": 888753760,   ← ここに数値を設定（null のまま進めるとエラーになる）
    ...
  },
  "みく": {
    "speaker_id": 123456789,   ← 別のキャラにも設定
    ...
  }
}
```

### Step 3 — 音声を生成する

```bash
uv run python run_poc.py
```

実行中は進捗が表示される:

```
AivisSpeech Engine: 1.0.0
[1/10] あかり: 今日はどんな論文を紹介してくれるの？
[2/10] みく: 今回はOpenAIのGPT-4 Technical Reportを…
...
完了！
  出力ファイル: output/final_episode.wav
  再生時間: 87.3秒 (1.5分)
```

### Step 4 — 出力を確認する

```bash
open output/final_episode.wav
```

---

## ファイル構成

```
voice-poc/
├── pyproject.toml      依存定義（requestsとpydub）
├── uv.lock             ロックファイル（uv sync で再現）
├── .python-version     Python 3.12 を指定
├── dialogue.json       台本（キャラ設定 + セリフ一覧）
├── list_speakers.py    スピーカーID確認スクリプト
├── synthesize.py       AivisSpeech API呼び出しモジュール
├── concat_audio.py     WAV連結モジュール
├── run_poc.py          エントリーポイント
└── output/             生成ファイル（実行時に自動作成）
    ├── line_000_あかり.wav
    ├── line_001_みく.wav
    ├── ...
    └── final_episode.wav  ← 最終成果物
```

---

## `dialogue.json` のフォーマット

台本はここを編集してカスタマイズする。

```json
{
  "title": "エピソードのタイトル（現在は出力に使われない）",
  "speakers": {
    "キャラ名A": {
      "speaker_id": 数値,          // list_speakers.py で確認したID
      "description": "メモ用の説明（プログラムは参照しない）",
      "params": {
        "speedScale": 1.05,        // 話速（0.5〜2.0、デフォルト1.0）
        "intonationScale": 1.3     // 感情の強さ（0.0〜2.0、デフォルト1.0）
      }
    },
    "キャラ名B": {
      "speaker_id": 数値,
      "description": "メモ用の説明",
      "params": {
        "speedScale": 0.95,
        "intonationScale": 1.1
      }
    }
  },
  "lines": [
    { "character": "キャラ名A", "text": "セリフ" },
    { "character": "キャラ名B", "text": "セリフ" }
  ]
}
```

### パラメータ調整のヒント

| パラメータ | 小さくすると | 大きくすると | PoC推奨値 |
|-----------|------------|------------|---------|
| `speedScale` | ゆっくり話す | 速く話す | 質問役: 1.05 / 専門家: 0.95 |
| `intonationScale` | フラット・落ち着く | 感情豊か・メリハリ強 | 質問役: 1.3 / 専門家: 1.1 |
| `pitchScale` | 低い声 | 高い声 | 未設定でOK（キャラ差はIDで出す） |
| `volumeScale` | 小さい | 大きい | 未設定でOK（デフォルト1.0） |

キャラ切替時の無音は `concat_audio.py` の `TURN_PAUSE_MS = 400`（ミリ秒）で調整できる。

---

## トラブルシューティング

### `ERROR: AivisSpeech Engineに接続できません`

AivisSpeech デスクトップアプリが起動していない。
アプリを起動してから再実行する。

### `ERROR: 'あかり' の speaker_id が未設定です`

`dialogue.json` の `speaker_id` が `null` のまま。
`list_speakers.py` でIDを確認して設定する。

### `list_speakers.py` で何も表示されない

AivisSpeech にボイスモデルがインストールされていない。
アプリのライブラリタブ、または AivisHub（https://hub.aivis-project.com/）からモデルをインストールする。

### pydub の警告 `Couldn't find ffmpeg`

WAV連結だけなら ffmpeg は不要なので無視してOK。
MP3に変換したい場合は `brew install ffmpeg` を実行する。

### 合成が遅い

モデルの初回ロードに時間がかかることがある（特に1行目）。
2行目以降は速くなるので、そのまま待つ。
