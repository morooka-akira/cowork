"""Google Cloud TTS Chirp3-HD でテキスト1行分の音声を生成する。"""

from __future__ import annotations

import io

from google.cloud import texttospeech
from pydub import AudioSegment

# Chirp3-HD の LINEAR16 はヘッダなし PCM。WAV として保存する。
CHIRP3_HD_SAMPLE_RATE_HZ = 24000


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
            sample_rate_hertz=CHIRP3_HD_SAMPLE_RATE_HZ,
            speaking_rate=float(p.get("speaking_rate", 1.0)),
        ),
    )

    pcm = response.audio_content
    segment = AudioSegment.from_raw(
        io.BytesIO(pcm),
        sample_width=2,
        frame_rate=CHIRP3_HD_SAMPLE_RATE_HZ,
        channels=1,
    )
    segment.export(output_path, format="wav")
    return output_path
