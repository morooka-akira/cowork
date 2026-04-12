"""行ごとの WAV を無音区切りで連結する。"""

from __future__ import annotations

from pydub import AudioSegment

TURN_PAUSE_MS = 400
FADE_MS = 15  # クリップ境界のプツプツ防止


def concat_wavs(wav_files: list[str], output_path: str) -> float:
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=TURN_PAUSE_MS, frame_rate=24000)

    for i, path in enumerate(wav_files):
        segment = AudioSegment.from_wav(path)
        segment = segment.fade_in(FADE_MS).fade_out(FADE_MS)
        if i > 0:
            combined += silence
        combined += segment

    combined.export(output_path, format="wav")
    duration_sec = len(combined) / 1000
    return duration_sec
