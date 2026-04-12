"""Gemini-TTS MultiSpeaker で対話台本を一括音声合成するエントリポイント。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import google.auth
import google.auth.exceptions
from google.cloud import texttospeech

ROOT = Path(__file__).resolve().parent


def check_credentials() -> None:
    try:
        google.auth.default()
    except google.auth.exceptions.DefaultCredentialsError:
        print("ERROR: Google Cloud認証が未設定です。")
        print("  → gcloud auth application-default login を実行してください。")
        sys.exit(1)
    print("Google Cloud 認証: OK")


def build_turns(
    lines: list[dict], speakers: dict
) -> list[texttospeech.MultiSpeakerMarkup.Turn]:
    return [
        texttospeech.MultiSpeakerMarkup.Turn(
            speaker=speakers[line["character"]]["speaker_alias"],
            text=line["text"],
        )
        for line in lines
    ]


def build_voice_configs(
    speakers: dict,
) -> list[texttospeech.MultispeakerPrebuiltVoice]:
    return [
        texttospeech.MultispeakerPrebuiltVoice(
            speaker_alias=info["speaker_alias"],
            speaker_id=info["voice_id"],
        )
        for info in speakers.values()
    ]


def main() -> None:
    check_credentials()

    with open(ROOT / "dialogue.json", encoding="utf-8") as f:
        script = json.load(f)

    speakers = script["speakers"]
    lines = script["lines"]
    total_chars = sum(len(line["text"]) for line in lines)
    print(f"\n台本: {len(lines)}行 / 約{total_chars}文字")

    turns = build_turns(lines, speakers)
    voice_configs = build_voice_configs(speakers)

    print("音声を生成中... (MultiSpeaker / 1回のAPIコール)")

    client = texttospeech.TextToSpeechClient()

    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(
            multi_speaker_markup=texttospeech.MultiSpeakerMarkup(turns=turns),
            prompt=script.get("style_prompt", ""),
        ),
        voice=texttospeech.VoiceSelectionParams(
            language_code=script["language_code"],
            model_name=script["model_name"],
            multi_speaker_voice_config=texttospeech.MultiSpeakerVoiceConfig(
                speaker_voice_configs=voice_configs,
            ),
        ),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            pitch=-2.0,
        ),
    )

    output_dir = ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "final_episode.mp3"

    with open(output_path, "wb") as f:
        f.write(response.audio_content)

    size_kb = output_path.stat().st_size // 1024
    print(f"\n完了！")
    print(f"  出力ファイル: {output_path}")
    print(f"  ファイルサイズ: {size_kb} KB")


if __name__ == "__main__":
    main()
