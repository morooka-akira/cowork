# Voice PoC: Gemini MultiSpeaker 設計まとめ

**ディレクトリ**: `poc/voice-multispeaker/`
**ステータス**: 動作確認済み・チューニング完了

---

## 概要

Google Cloud TTS の **Gemini 2.5 Pro TTS MultiSpeaker** を使って、2人の女性キャラクターによるポッドキャスト形式の音声を生成するPoC。

前段の Chirp3-HD PoC（行ごとの逐次合成）と比べて、**会話全体を1回のAPIコールで生成**することでイントネーションと掛け合いの自然さが大幅に改善した。

---

## アーキテクチャ

### 生成フロー

```
dialogue.json
  ├── style_prompt      → SynthesisInput.prompt
  ├── speakers          → MultiSpeakerVoiceConfig.speaker_voice_configs
  └── lines             → MultiSpeakerMarkup.turns
          ↓
  TextToSpeechClient.synthesize_speech()  ← 1回のAPIコール
          ↓
  output/final_episode.mp3
```

### API構造（重要な配置）

```python
client.synthesize_speech(
    input=SynthesisInput(
        multi_speaker_markup=MultiSpeakerMarkup(turns=[...]),
        prompt=style_prompt,          # ← SynthesisInput の中
    ),
    voice=VoiceSelectionParams(
        language_code="ja-JP",
        model_name="gemini-2.5-pro-tts",
        multi_speaker_voice_config=MultiSpeakerVoiceConfig(
            speaker_voice_configs=[...],   # ← VoiceSelectionParams の中
        ),
    ),
    audio_config=AudioConfig(
        audio_encoding=AudioEncoding.MP3,
        pitch=-2.0,
    ),
)
```

> `multi_speaker_voice_config` は `VoiceSelectionParams` の中に置く。`SynthesizeSpeechRequest` の直下に置くとエラー（ハマりポイント）。

---

## 確定パラメータ

### キャラクター設定

| 項目 | あかり（Akari） | みく（Miku） |
|---|---|---|
| 役割 | 誘導役・聞き役 | 答え役・解説役 |
| voice_id | `Achernar` | `Despina` |
| 年齢感 | 13〜14歳・アニメ的な透明感 | 18歳・明るく落ち着いたお姉さん |
| 話し方 | おとなしめ・控えめ・`...`で間 | 流れるように・`——`で緩急・`！`で強調 |

### style_prompt（確定版）

```
これは女の子2人によるポッドキャスト番組。
Akariは13〜14歳くらいの透明感のある声で、アニメキャラのようなやや細くて澄んだトーン。おとなしめで控えめな話し方をする。
Mikuは18歳くらいの少し大人なお姉さんで、声は明るくて聴きやすいが落ち着いていて安定感がある。
AkariとMikuは声の年齢感・音域・トーンが明確に異なり、聞き手がすぐに区別できる。
```

### AudioConfig

| パラメータ | 値 | 備考 |
|---|---|---|
| `audio_encoding` | `MP3` | |
| `pitch` | `-2.0` | 全体を2半音下げ。Gemini TTS で有効（Chirp3-HD は非対応） |

---

## 声質チューニングの知見

### ボイスIDの選び方
- MultiSpeaker では **2話者の組み合わせ全体**を一括生成するため、単体サンプルと実際の出力で声質が変わる
- サンプル生成時は必ず**実際のパートナーボイスと組み合わせて**生成する（`sample_voices.py` 参照）
- 今回の探索結果（Achernarとのペア）:
  - `Erinome` — クリアで聴きやすい（最終候補）
  - `Despina` — 落ち着いたやわらかさ（採用）
  - `Callirrhoe` — 友好的・ファイルサイズ大きめ
  - `Kore` / `Zephyr` — 声質が似すぎてコントラスト不足

### テキスト表現による声質誘導
style_prompt だけでなく、**テキストの書き方が声のトーンに強く影響する**。

| 表現 | 効果 |
|---|---|
| `...` | 間・躊躇・静かなリアクション |
| `〜` | 語尾を伸ばす・やわらかさ |
| `——` | 自然な間・テンポの緩急 |
| `！` | 強調・ポイントを際立てる |
| 口語的な言い回し | 全体の声の年齢感を若くする |

> 技術用語が多い台本は、周囲の文体が硬いとモデルが声を大人っぽくシフトさせる。  
> キーワードは保持しつつ **周辺の文体を崩す**ことで若い声質を維持できる。

### style_prompt の限界
- 声の年齢感・キャラクターの印象は制御できる
- **話者ごとに** speaking_rate / pitch を変えることはできない（AudioConfig は全体適用）
- pitch は全体に効くため、コントラストは style_prompt + voice_id の組み合わせで出す

---

## ファイル構成

```
poc/voice-multispeaker/
├── pyproject.toml          # google-cloud-texttospeech, google-auth
├── .python-version         # 3.12
├── dialogue.json           # 台本・話者設定・style_prompt
├── run_poc.py              # エントリーポイント
├── sample_voices.py        # 全女性ボイスのサンプル一括生成
└── content/
    └── neural_computers_outline.md   # 論文要約・台本構成メモ
```

---

## セットアップ

```bash
# 1. 認証（初回のみ）
gcloud auth application-default login
gcloud auth application-default set-quota-project oyako-story

# 2. 依存インストール
cd poc/voice-multispeaker
uv sync

# 3. 実行
uv run python run_poc.py

# 4. ボイス探索（声を変えたいとき）
uv run python sample_voices.py
open output/samples/
```

---

## Chirp3-HD との比較

| | Chirp3-HD | Gemini MultiSpeaker |
|---|---|---|
| 合成方式 | 行ごとに逐次API呼び出し | 会話全体を1回で生成 |
| イントネーション | フラット（文脈なし） | 会話の流れが乗る |
| 話者間の自然な間 | pydubで手動挿入 | モデルが自動で調整 |
| 声質の制御 | voice_name + speaking_rate | voice_id + style_prompt + pitch |
| コスト | 同等（文字数課金） | 同等 |
| 結論 | PoC止まり | **こちらを採用** |

---

## 課題・今後

- [ ] 台本生成の自動化（論文PDF → dialogue.json を LLM で生成）
- [ ] 複数エピソードのバッチ生成
- [ ] BGM・イントロ音楽の追加（pydub で合成）
- [ ] style_prompt と voice_id の組み合わせをパラメータ化して再利用しやすくする
