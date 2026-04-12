"""Gemini-TTS の女性ボイスを一括サンプル生成するスクリプト。"""

from __future__ import annotations

import sys
from pathlib import Path

import google.auth
import google.auth.exceptions
from google.cloud import texttospeech

ROOT = Path(__file__).resolve().parent

# gemini-2.5-pro-tts の女性ボイス候補
FEMALE_VOICES = [
    "Zephyr",
    "Kore",
    "Aoede",
    "Leda",
    "Sulafat",
    "Callirrhoe",
    "Autonoe",
    "Despina",
    "Erinome",
    "Gacrux",
    "Laomedeia",
    "Pulcherrima",
    "Vindemiatrix",
    "Achernar",
]

# S1 = みく候補（話し役）のサンプルテキスト
SAMPLE_TEXT_S1 = (
    "エージェントって外のツールとかAPIを呼びながら動くんだけど、"
    "NCは全部内側で完結するの。完全に実現したやつをCNCって言って、"
    "チューリング完全とか、behavior-consistentとか、4つの条件がそろって初めてCNCって呼べる。"
)

# S2 = あかり固定（Achernar）
PARTNER_VOICE = "Achernar"
PARTNER_TEXT = "AIエージェントとはどう違うの？なんか似てない？"

# style_prompt は dialogue.json に合わせる
STYLE_PROMPT = (
    "これは10代後半の女の子2人によるポッドキャスト番組。"
    "S2はちょっと天然でポケっとした高校生っぽいキャラクター。声は軽くて若い。"
    "S1は同世代の落ち着いた子で、声はやわらかくて聴き心地がいい。透き通るような透明感がある。"
    "ふたりとも声は若々しく、大人の女性のトーンは出さない。"
)

MODEL_NAME = "gemini-2.5-pro-tts"
LANGUAGE_CODE = "ja-JP"


def check_credentials() -> None:
    try:
        google.auth.default()
    except google.auth.exceptions.DefaultCredentialsError:
        print("ERROR: Google Cloud認証が未設定です。")
        print("  → gcloud auth application-default login を実行してください。")
        sys.exit(1)
    print("Google Cloud 認証: OK\n")


def generate_sample(
    client: texttospeech.TextToSpeechClient,
    voice_name: str,
    output_path: Path,
) -> None:
    # 実際のエピソードに近い環境で評価するため:
    # - S1 = テスト対象ボイス（聞き役）
    # - S2 = Achernar 固定（話し役）
    # - style_prompt も実際の設定に合わせる
    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(
            multi_speaker_markup=texttospeech.MultiSpeakerMarkup(
                turns=[
                    texttospeech.MultiSpeakerMarkup.Turn(
                        speaker="S1",
                        text=SAMPLE_TEXT_S1,
                    ),
                    texttospeech.MultiSpeakerMarkup.Turn(
                        speaker="S2",
                        text=PARTNER_TEXT,
                    ),
                ]
            ),
            prompt=STYLE_PROMPT,
        ),
        voice=texttospeech.VoiceSelectionParams(
            language_code=LANGUAGE_CODE,
            model_name=MODEL_NAME,
            multi_speaker_voice_config=texttospeech.MultiSpeakerVoiceConfig(
                speaker_voice_configs=[
                    texttospeech.MultispeakerPrebuiltVoice(
                        speaker_alias="S1",
                        speaker_id=voice_name,
                    ),
                    texttospeech.MultispeakerPrebuiltVoice(
                        speaker_alias="S2",
                        speaker_id=PARTNER_VOICE,
                    ),
                ]
            ),
        ),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
        ),
    )
    with open(output_path, "wb") as f:
        f.write(response.audio_content)


def main() -> None:
    check_credentials()

    output_dir = ROOT / "output" / "samples"
    output_dir.mkdir(parents=True, exist_ok=True)

    client = texttospeech.TextToSpeechClient()

    success = []
    failed = []

    for voice_name in FEMALE_VOICES:
        output_path = output_dir / f"{voice_name}.mp3"
        print(f"  生成中: {voice_name:<20}", end="", flush=True)
        try:
            generate_sample(client, voice_name, output_path)
            size_kb = output_path.stat().st_size // 1024
            print(f"→ OK ({size_kb} KB)")
            success.append(voice_name)
        except Exception as e:
            print(f"→ FAILED: {e}")
            failed.append((voice_name, str(e)))

    print(f"\n完了: {len(success)}/{len(FEMALE_VOICES)} 件成功")
    print(f"出力先: {output_dir}")
    if failed:
        print("\n失敗したボイス:")
        for name, err in failed:
            print(f"  {name}: {err}")


if __name__ == "__main__":
    main()
