"""ja-JP の Chirp3-HD ボイス一覧を表示する。"""

from __future__ import annotations

from google.cloud import texttospeech
from google.cloud.texttospeech import SsmlVoiceGender


def _gender_label(g: SsmlVoiceGender) -> str:
    return {
        SsmlVoiceGender.MALE: "MALE",
        SsmlVoiceGender.FEMALE: "FEMALE",
        SsmlVoiceGender.NEUTRAL: "NEUTRAL",
        SsmlVoiceGender.SSML_VOICE_GENDER_UNSPECIFIED: "?",
    }.get(g, "?")


def main() -> None:
    client = texttospeech.TextToSpeechClient()
    resp = client.list_voices(language_code="ja-JP")

    print(f"{'ボイス名':<35} {'性別'}")
    print("-" * 50)
    for v in sorted(resp.voices, key=lambda x: x.name):
        if "Chirp3-HD" in v.name:
            print(f"{v.name:<35} {_gender_label(v.ssml_gender)}")


if __name__ == "__main__":
    main()
