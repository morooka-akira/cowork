"""台本 JSON から対話 WAV を一括生成するエントリポイント。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

from concat_audio import concat_wavs
from synthesize import generate_line

API_BASE = "http://127.0.0.1:10101"
ROOT = Path(__file__).resolve().parent


def check_engine() -> None:
    try:
        resp = requests.get(f"{API_BASE}/version", timeout=3)
        resp.raise_for_status()
    except Exception:
        print("ERROR: AivisSpeech Engineに接続できません。アプリを起動してください。")
        sys.exit(1)

    try:
        data = resp.json()
        if isinstance(data, dict) and "version" in data:
            print(f"AivisSpeech Engine: {data['version']}")
        else:
            print(f"AivisSpeech Engine: {data}")
    except requests.exceptions.JSONDecodeError:
        print(f"AivisSpeech Engine: {resp.text.strip()}")


def resolve_speaker_ids(speakers_config: dict) -> dict:
    """speaker_uuid → 最初のスタイルの style_id (int) に解決する。"""
    resp = requests.get(f"{API_BASE}/speakers", timeout=30)
    resp.raise_for_status()
    all_speakers = resp.json()

    uuid_to_style: dict[str, tuple[int, str]] = {}
    for speaker in all_speakers:
        uuid = speaker.get("speaker_uuid", "")
        if speaker.get("styles"):
            first = speaker["styles"][0]
            uuid_to_style[uuid] = (first["id"], first["name"])

    resolved: dict[str, dict] = {}
    for char, info in speakers_config.items():
        info = dict(info)
        uuid = info.get("speaker_uuid")
        if uuid:
            if uuid not in uuid_to_style:
                print(f"ERROR: '{char}' の speaker_uuid '{uuid}' が見つかりません。")
                print("\nインストール済みスピーカーのUUID一覧:")
                for s in all_speakers:
                    print(f"  {s.get('name',''):<20} {s.get('speaker_uuid','')}")
                sys.exit(1)
            style_id, style_name = uuid_to_style[uuid]
            info["speaker_id"] = style_id
            print(f"  {char}: uuid={uuid[:8]}… → style_id={style_id} ({style_name})")
        elif info.get("speaker_id") is None:
            print(f"ERROR: '{char}' の speaker_uuid も speaker_id も未設定です。")
            sys.exit(1)
        resolved[char] = info

    return resolved


def main() -> None:
    check_engine()

    dialogue_path = ROOT / "dialogue.json"
    with open(dialogue_path, encoding="utf-8") as f:
        script = json.load(f)

    print("\nスピーカーIDを解決中...")
    speakers = resolve_speaker_ids(script["speakers"])
    lines = script["lines"]

    output_dir = ROOT / "output"
    output_dir.mkdir(exist_ok=True)

    print("\n音声を生成中...")
    wav_files: list[str] = []
    for i, line in enumerate(lines):
        character = line["character"]
        text = line["text"]
        speaker_info = speakers[character]
        speaker_id = speaker_info["speaker_id"]
        params = speaker_info.get("params", {})

        output_path = str(output_dir / f"line_{i:03d}_{character}.wav")
        preview = text[:40] + ("…" if len(text) > 40 else "")
        print(f"[{i + 1}/{len(lines)}] {character}: {preview}")
        generate_line(text, speaker_id, output_path, params)
        wav_files.append(output_path)

    final_path = str(output_dir / "final_episode.wav")
    duration = concat_wavs(wav_files, final_path)

    print("\n完了！")
    print(f"  出力ファイル: {final_path}")
    print(f"  再生時間: {duration:.1f}秒 ({duration / 60:.1f}分)")


if __name__ == "__main__":
    main()
