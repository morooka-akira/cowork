"""AivisSpeech Engine のスピーカー（スタイル）一覧を表示する。"""

import requests

API_BASE = "http://127.0.0.1:10101"


def main() -> None:
    resp = requests.get(f"{API_BASE}/speakers", timeout=30)
    resp.raise_for_status()
    speakers = resp.json()

    print(f"{'style_id':>10}  {'スピーカー名':<20} {'スタイル名':<16} speaker_uuid")
    print("-" * 90)
    for speaker in speakers:
        uuid = speaker.get("speaker_uuid", "")
        for style in speaker["styles"]:
            print(f"{style['id']:>10}  {speaker['name']:<20} {style['name']:<16} {uuid}")


if __name__ == "__main__":
    main()
