"""AivisSpeech Engine へ HTTP で問い合わせ、1行分の WAV を生成する。"""

from __future__ import annotations

import requests

API_BASE = "http://127.0.0.1:10101"


def audio_query(text: str, speaker_id: int, params: dict | None = None) -> dict:
    # 公式仕様: text / speaker はクエリパラメータ（POST body の form ではない）
    resp = requests.post(
        f"{API_BASE}/audio_query",
        params={"text": text, "speaker": speaker_id},
        timeout=120,
    )
    resp.raise_for_status()
    query = resp.json()

    if params:
        query.update(params)

    return query


def synthesis(query: dict, speaker_id: int) -> bytes:
    resp = requests.post(
        f"{API_BASE}/synthesis",
        params={"speaker": speaker_id},
        json=query,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.content


def generate_line(
    text: str,
    speaker_id: int,
    output_path: str,
    params: dict | None = None,
) -> str:
    query = audio_query(text, speaker_id, params)
    wav_data = synthesis(query, speaker_id)
    with open(output_path, "wb") as f:
        f.write(wav_data)
    return output_path
