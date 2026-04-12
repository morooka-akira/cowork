# 設計ドキュメント: AivisSpeech 女性音声 PoC

> ステータス: 設計完了・実装待ち
> 作成日: 2026-04-12
> 関連アイデア: `ideas/ai-paper-podcast.md`

---

## 目的

「AI論文 深掘り対談ポッドキャスト」の Phase 0 として、
2名の女性キャラが対談するポッドキャスト音声を **AivisSpeech Engine** で生成できることを検証する。

**PoC完了の定義:**
- テキスト台本（JSON）を入力すると、2人の声が交互に話す1本のWAVファイルが出力される
- 再生して「聞いてて違和感ない」レベルの音質・自然さを確認できる

---

## 技術スタック

| 要素 | 選定 | 理由 |
|------|------|------|
| 音声合成エンジン | AivisSpeech Engine | 高品質な日本語TTS、感情表現対応、VOICEVOXライクなAPI |
| API通信 | Python + requests | シンプル、依存が少ない |
| 音声連結 | pydub | WAV操作・無音挿入・MP3変換が容易 |
| 台本フォーマット | JSON | 拡張性があり、将来的なLLM生成台本と接続しやすい |

---

## AivisSpeech Engine API仕様（確認済み）

**基本情報:**
- ローカルサーバー: `http://127.0.0.1:10101`
- 起動方法: AivisSpeech デスクトップアプリを起動するだけ（自動的にエンジンが立ち上がる）
- API仕様書: `http://127.0.0.1:10101/docs`（Swagger UI）

**音声合成フロー:**

```
1. GET  /speakers                        → スピーカー一覧取得（speaker_uuid, style_id, name）
2. POST /audio_query?speaker={style_id}  → テキスト → AudioQueryパラメータJSON
3. POST /synthesis?speaker={style_id}   → AudioQueryJSON → WAVバイナリ
```

**調整可能なパラメータ（AudioQuery）:**

| パラメータ | デフォルト | 範囲 | 用途 |
|---|---|---|---|
| `speedScale` | 1.0 | 0.5〜2.0 | 話速 |
| `pitchScale` | 0.0 | -0.15〜0.15 | 音程 |
| `intonationScale` | 1.0 | 0.0〜2.0 | 感情の強さ |
| `volumeScale` | 1.0 | 0.0〜2.0 | 音量 |
| `tempoDynamicsScale` | 1.0 | 0.0〜2.0 | 音声の躍動感 |

**PoC推奨パラメータ:**
- `intonationScale: 1.2` — 対話らしい自然な感情表現
- `speedScale: 1.0` — 標準速度（後で調整）

---

## ディレクトリ構成

```
strategy/poc/voice-poc/
├── pyproject.toml          # 依存定義（uv）
├── uv.lock                 # ロックファイル（uv sync で再現）
├── .python-version         # Python バージョン（uv が参照）
├── dialogue.json           # サンプル台本（2キャラ対談）
├── list_speakers.py        # スピーカーID確認スクリプト
├── synthesize.py           # コア合成モジュール
├── concat_audio.py         # 音声連結モジュール
└── run_poc.py              # エントリーポイント（全ステップ一括実行）
```

### `output/` ディレクトリ（実行時に自動生成）

```
output/
├── line_000_あかり.wav
├── line_001_みく.wav
├── ...
└── final_episode.wav       ← 最終成果物
```

---

## 各ファイルの仕様

### `dialogue.json`

2名の女性キャラによるGPT-4論文解説。対談の構造を検証できる8〜12行を想定。

```json
{
  "title": "GPT-4 Technicalを5分で深掘り",
  "speakers": {
    "あかり": {
      "speaker_id": null,
      "description": "質問役・好奇心旺盛・明るい声",
      "params": { "speedScale": 1.05, "intonationScale": 1.3 }
    },
    "みく": {
      "speaker_id": null,
      "description": "専門家役・落ち着いた声・知的",
      "params": { "speedScale": 0.95, "intonationScale": 1.1 }
    }
  },
  "lines": [
    { "character": "あかり", "text": "今日はどんな論文を紹介してくれるの？" },
    { "character": "みく",   "text": "今回はOpenAIのGPT-4 Technical Reportを取り上げます。2023年に公開された、大規模言語モデルの能力と安全性を詳しく報告した論文です。" },
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

> `speaker_id` は `list_speakers.py` を実行して確認後、手動で設定する。

### `list_speakers.py`

```python
import requests

API_BASE = "http://127.0.0.1:10101"

def main():
    resp = requests.get(f"{API_BASE}/speakers")
    resp.raise_for_status()
    speakers = resp.json()
    
    print(f"{'ID':>6}  {'スピーカー名':<20} {'スタイル名'}")
    print("-" * 50)
    for speaker in speakers:
        for style in speaker["styles"]:
            print(f"{style['id']:>6}  {speaker['name']:<20} {style['name']}")

if __name__ == "__main__":
    main()
```

### `synthesize.py`

```python
import requests

API_BASE = "http://127.0.0.1:10101"

def audio_query(text: str, speaker_id: int, params: dict = None) -> dict:
    resp = requests.post(
        f"{API_BASE}/audio_query",
        params={"speaker": speaker_id},
        data={"text": text}
    )
    resp.raise_for_status()
    query = resp.json()
    
    # キャラクター別パラメータを適用
    if params:
        query.update(params)
    
    return query

def synthesis(query: dict, speaker_id: int) -> bytes:
    resp = requests.post(
        f"{API_BASE}/synthesis",
        params={"speaker": speaker_id},
        json=query
    )
    resp.raise_for_status()
    return resp.content

def generate_line(text: str, speaker_id: int, output_path: str, params: dict = None):
    query = audio_query(text, speaker_id, params)
    wav_data = synthesis(query, speaker_id)
    with open(output_path, "wb") as f:
        f.write(wav_data)
    return output_path
```

### `concat_audio.py`

```python
from pydub import AudioSegment

TURN_PAUSE_MS = 400   # キャラ切替時の無音（ミリ秒）

def concat_wavs(wav_files: list[str], output_path: str):
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=TURN_PAUSE_MS)
    
    for i, path in enumerate(wav_files):
        segment = AudioSegment.from_wav(path)
        if i > 0:
            combined += silence
        combined += segment
    
    combined.export(output_path, format="wav")
    duration_sec = len(combined) / 1000
    return duration_sec
```

### `run_poc.py`

```python
import json
import sys
import requests
from pathlib import Path
from synthesize import generate_line
from concat_audio import concat_wavs

API_BASE = "http://127.0.0.1:10101"

def check_engine():
    try:
        resp = requests.get(f"{API_BASE}/version", timeout=3)
        version = resp.json()
        print(f"AivisSpeech Engine: v{version}")
    except Exception:
        print("ERROR: AivisSpeech Engineに接続できません。アプリを起動してください。")
        sys.exit(1)

def main():
    check_engine()
    
    with open("dialogue.json", encoding="utf-8") as f:
        script = json.load(f)
    
    speakers = script["speakers"]
    lines = script["lines"]
    
    # speaker_id 未設定チェック
    for char, info in speakers.items():
        if info["speaker_id"] is None:
            print(f"ERROR: '{char}' の speaker_id が未設定です。")
            print("  → python list_speakers.py で確認し、dialogue.json に設定してください。")
            sys.exit(1)
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    wav_files = []
    for i, line in enumerate(lines):
        character = line["character"]
        text = line["text"]
        speaker_info = speakers[character]
        speaker_id = speaker_info["speaker_id"]
        params = speaker_info.get("params", {})
        
        output_path = str(output_dir / f"line_{i:03d}_{character}.wav")
        print(f"[{i+1}/{len(lines)}] {character}: {text[:40]}...")
        generate_line(text, speaker_id, output_path, params)
        wav_files.append(output_path)
    
    final_path = str(output_dir / "final_episode.wav")
    duration = concat_wavs(wav_files, final_path)
    
    print(f"\n完了！")
    print(f"  出力ファイル: {final_path}")
    print(f"  再生時間: {duration:.1f}秒 ({duration/60:.1f}分)")

if __name__ == "__main__":
    main()
```

### `pyproject.toml` / `uv.lock`

依存は `pyproject.toml` に宣言し、`uv lock` で `uv.lock` を更新する。実行は `uv sync` で `.venv` に同期。

> MP3エクスポートが必要な場合: `brew install ffmpeg`

---

## セットアップ手順（実行時）

```bash
# 0. 未インストールなら: https://docs.astral.sh/uv/getting-started/installation/

# 1. AivisSpeech デスクトップアプリを起動（エンジンが自動起動）

# 2. 依存を同期（プロジェクト直下に .venv ができる）
cd strategy/poc/voice-poc
uv sync

# 3. スピーカー一覧を確認して女性ボイスのIDを選ぶ
uv run python list_speakers.py

# 4. dialogue.json の speaker_id に2つのIDを設定
#    例: "あかり": { "speaker_id": 888753760 }

# 5. PoC実行
uv run python run_poc.py

# 6. 出力を確認
open output/final_episode.wav
```

---

## 評価基準（PoC後に判定）

| 評価項目 | 基準 |
|------|------|
| 音質 | 聞いていて不快感がないか |
| 自然さ | 棒読み感が少ないか、抑揚があるか |
| キャラの差別化 | 2人の声が明確に区別できるか |
| 感情表現 | 質問・驚き・説明など文脈に合っているか |
| 総合 | 「NotebookLMより面白い」と思えるか |

---

## 次のステップ（PoC通過後）

1. **ボイスの最終選定** — 複数の女性ボイスを試して2キャラを確定
2. **台本生成の自動化** — LLM（Claude）で論文 → 対談台本を生成するプロンプト設計
3. **完全パイプライン化** — 論文PDF入力 → 音声ファイル出力まで一気通貫
4. **配信フォーマット確定** — OP/ED・BGM・MP3変換・メタデータ付与

---

## リスク・注意点

| リスク | 対処 |
|------|------|
| AivisSpeechのスピーカー音質が期待以下 | AivisHubで追加モデルをインストールして試す |
| pydubのffmpegがない環境でMP3変換失敗 | PoC段階はWAVのみでOK |
| speaker_id がインストールモデルによって変わる | `list_speakers.py` で毎回確認する |
