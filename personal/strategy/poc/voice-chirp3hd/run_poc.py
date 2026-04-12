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
