# 設計ドキュメント: Google Cloud TTS Chirp3-HD 女性音声 PoC

> ステータス: 実装済み（`poc/voice-chirp3hd/`）
> 作成日: 2026-04-12
> 関連: `poc/voice-poc/`（AivisSpeech版）との比較用

---

## 目的

AivisSpeech PoC（`poc/voice-poc/`）と同一の台本シナリオを、
Google Cloud Text-to-Speech **Chirp3-HD** の女性ボイスで読み上げる。
2つのTTSエンジンの音質・自然さ・運用コストを比較するための対照PoC。

---

## 技術スタック

| 要素 | 選定 |
|------|------|
| 音声合成 | Google Cloud TTS Chirp3-HD |
| Python SDK | `google-cloud-texttospeech` |
| 認証 | Application Default Credentials（ADC） |
| 音声連結 | pydub（voice-pocと同一） |
| 環境管理 | uv |

---

## Chirp3-HD API仕様

**日本語女性ボイス一覧:**

| voice_name | 特徴（推測） |
|---|---|
| `ja-JP-Chirp3-HD-Aoede` | 明るい・会話向き |
| `ja-JP-Chirp3-HD-Kore` | 落ち着いた・説明向き |
| `ja-JP-Chirp3-HD-Leda` | 柔らかい |
| `ja-JP-Chirp3-HD-Zephyr` | 爽やかな |

**調整可能なパラメータ（`AudioConfig`）:**

| パラメータ | 範囲 | デフォルト | 用途 |
|---|---|---|---|
| `speaking_rate` | 0.25〜2.0 | 1.0 | 話速 |
| `pitch` | -20〜+20 | 0.0 | 音程（半音単位） |

> `intonationScale` や `tempoDynamicsScale` に相当するパラメータはない。
> キャラの個性差は voice_name の選択 + pitch で出す。

**出力フォーマット:**
- `LINEAR16`（16bit PCM）を使用 → pydub でそのまま連結可能
- サンプリングレート: 24000Hz（Chirp3-HD のデフォルト）

**料金:**
- 月100万文字まで無料（HD tier）
- 超過分: $0.000016 / 文字（10万文字 ≈ $1.6）
- PoC規模（数百文字）は実質無料

---

## ディレクトリ構成

```
poc/voice-chirp3hd/
├── pyproject.toml       # 依存定義（uv）
├── uv.lock
├── .python-version      # 3.12
├── dialogue.json        # 同一台本・Chirp3-HD用speaker設定
├── list_voices.py       # ja-JP Chirp3-HDボイス一覧表示
├── synthesize.py        # Google Cloud TTS呼び出しモジュール
├── concat_audio.py      # WAV連結（voice-pocと同一コード）
└── run_poc.py           # エントリーポイント
```

```
output/                  # 実行時に自動生成
├── line_000_あかり.wav
├── line_001_みく.wav
├── ...
└── final_episode.wav    ← 最終成果物
```

---

## 各ファイルの仕様

### `pyproject.toml`

```toml
[project]
name = "voice-chirp3hd"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "google-cloud-texttospeech>=2.16.0",
    "pydub>=0.25.1",
    "google-auth>=2.0.0",
]

[tool.uv]
package = false
```

### `dialogue.json`

`poc/voice-poc/dialogue.json` と台本テキスト（lines）は同一。
speaker設定のキーのみChirp3-HD仕様に変更。

```json
{
  "title": "GPT-4 Technicalを5分で深掘り",
  "speakers": {
    "あかり": {
      "voice_name": "ja-JP-Chirp3-HD-Aoede",
      "description": "パーソナリティ側・好奇心旺盛",
      "params": {
        "speaking_rate": 1.05,
        "pitch": 1.0
      }
    },
    "みく": {
      "voice_name": "ja-JP-Chirp3-HD-Kore",
      "description": "回答側・落ち着いた声・知的",
      "params": {
        "speaking_rate": 0.9,
        "pitch": -1.0
      }
    }
  },
  "lines": [
    { "character": "あかり", "text": "今日はどんな論文を紹介してくれるの？" },
    { "character": "みく",   "text": "今回は、オープンエーアイのジーピーティーフォー テクニカルレポートを取り上げます。2023年に公開された、大規模言語モデルの能力と安全性を詳しく報告した論文です。" },
    { "character": "あかり", "text": "GPT-4って有名だけど、論文で何がすごいの？" },
    { "character": "みく",   "text": "一番のポイントは『スケーリングの予測可能性』です。学習データを増やすほど性能が予測通りに上がる、という関係性を実証したんです。" },
    { "character": "あかり", "text": "なるほど。実際のビジネスだとどう使えるの？" },
    { "character": "みく",   "text": "マルチモーダル、つまり画像とテキストを同時に扱える点が実務で大きいですね。医療画像の解釈や、書類の自動処理に既に使われています。" },
    { "character": "あかり", "text": "じゃあ、逆に限界や課題は？" },
    { "character": "みく",   "text": "幻覚問題、つまり自信満々に間違いを言うリスクは依然として残ります。あと、推論コストが高いので、使い所を絞る必要があります。" },
    { "character": "あかり", "text": "ありがとう！要するに、すごく賢くなったけど、使い方を設計するのが大事ってことだね。" },
    { "character": "みく",   "text": "その通りです。能力と限界の両方を理解した上で設計するエンジニアが、これからますます重要になりますね。" }
  ]
}
```

### `list_voices.py`

```python
"""ja-JP の Chirp3-HD ボイス一覧を表示する。"""
from google.cloud import texttospeech

def main():
    client = texttospeech.TextToSpeechClient()
    resp = client.list_voices(language_code="ja-JP")

    print(f"{'ボイス名':<35} {'性別'}")
    print("-" * 50)
    for v in sorted(resp.voices, key=lambda v: v.name):
        if "Chirp3-HD" in v.name:
            gender = {1: "MALE", 2: "FEMALE", 3: "NEUTRAL"}.get(v.ssml_gender, "?")
            print(f"{v.name:<35} {gender}")

if __name__ == "__main__":
    main()
```

### `synthesize.py`

```python
"""Google Cloud TTS Chirp3-HD でテキスト1行分の音声を生成する。"""
from google.cloud import texttospeech

def generate_line(
    text: str,
    voice_name: str,
    output_path: str,
    params: dict | None = None,
) -> str:
    client = texttospeech.TextToSpeechClient()
    p = params or {}

    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=texttospeech.VoiceSelectionParams(
            language_code="ja-JP",
            name=voice_name,
        ),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            speaking_rate=p.get("speaking_rate", 1.0),
            pitch=p.get("pitch", 0.0),
        ),
    )

    with open(output_path, "wb") as f:
        f.write(response.audio_content)
    return output_path
```

### `concat_audio.py`

`poc/voice-poc/concat_audio.py` と同一。

```python
"""行ごとの WAV を無音区切りで連結する。"""
from pydub import AudioSegment

TURN_PAUSE_MS = 400

def concat_wavs(wav_files: list[str], output_path: str) -> float:
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=TURN_PAUSE_MS)

    for i, path in enumerate(wav_files):
        segment = AudioSegment.from_wav(path)
        if i > 0:
            combined += silence
        combined += segment

    combined.export(output_path, format="wav")
    return len(combined) / 1000
```

> Google TTS の `LINEAR16` はヘッダなし RAW で返る場合がある。
> その場合は `from_wav` → `from_raw(path, sample_width=2, frame_rate=24000, channels=1)` でフォールバックする。
> 実際に発生したら `run_poc.py` 側で対応する。

### `run_poc.py`

```python
"""台本 JSON から対話 WAV を一括生成するエントリポイント（Chirp3-HD版）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import google.auth
import google.auth.exceptions

from concat_audio import concat_wavs
from synthesize import generate_line

ROOT = Path(__file__).resolve().parent


def check_credentials() -> None:
    try:
        google.auth.default()
    except google.auth.exceptions.DefaultCredentialsError:
        print("ERROR: Google Cloud認証が未設定です。")
        print("  → gcloud auth application-default login を実行してください。")
        sys.exit(1)
    print("Google Cloud 認証: OK")


def main() -> None:
    check_credentials()

    with open(ROOT / "dialogue.json", encoding="utf-8") as f:
        script = json.load(f)

    speakers = script["speakers"]
    lines = script["lines"]

    output_dir = ROOT / "output"
    output_dir.mkdir(exist_ok=True)

    print(f"\n音声を生成中... ({len(lines)}行)")
    wav_files: list[str] = []
    for i, line in enumerate(lines):
        character = line["character"]
        text = line["text"]
        voice_name = speakers[character]["voice_name"]
        params = speakers[character].get("params", {})

        output_path = str(output_dir / f"line_{i:03d}_{character}.wav")
        preview = text[:40] + ("…" if len(text) > 40 else "")
        print(f"[{i + 1}/{len(lines)}] {character} ({voice_name}): {preview}")
        generate_line(text, voice_name, output_path, params)
        wav_files.append(output_path)

    final_path = str(output_dir / "final_episode.wav")
    duration = concat_wavs(wav_files, final_path)

    print("\n完了！")
    print(f"  出力ファイル: {final_path}")
    print(f"  再生時間: {duration:.1f}秒 ({duration / 60:.1f}分)")


if __name__ == "__main__":
    main()
```

---

## セットアップ手順

```bash
# 1. Google Cloud 認証（初回のみ）
gcloud auth application-default login

# 2. 依存をインストール
cd poc/voice-chirp3hd
uv sync

# 3. 利用可能なボイス確認（任意）
uv run python list_voices.py

# 4. PoC実行
uv run python run_poc.py

# 5. 出力確認
open output/final_episode.wav
```

---

## voice-poc（AivisSpeech）との差分

| 要素 | voice-poc | voice-chirp3hd |
|---|---|---|
| エンジン | ローカル（AivisSpeech） | クラウド（Google） |
| 事前準備 | アプリ起動 | `gcloud auth` |
| speaker識別子 | `speaker_uuid` → style_id（整数） | `voice_name` 文字列を直接使用 |
| 感情パラメータ | intonationScale, tempoDynamicsScale | なし（pitch で代替） |
| 出力ファイル | WAV（ヘッダあり） | LINEAR16（RAWの可能性あり） |
| コスト | 無料 | 月100万文字まで無料 |
| プライバシー | テキストがローカルで完結 | Googleにテキストを送信 |

---

## 比較評価の観点（PoC後）

| 評価項目 | 着眼点 |
|---|---|
| 音質 | Chirp3-HD vs AivisSpeech、どちらが聞き取りやすいか |
| 自然さ | 抑揚・感情表現のリアルさ |
| キャラ差 | 2人の声が明確に区別できるか |
| 日本語対応 | カタカナ語・専門用語の発音精度 |
| 運用コスト | 月100万文字超のコスト試算 |
| レイテンシ | 1行あたりの生成時間 |
