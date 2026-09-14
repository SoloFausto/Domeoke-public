"""Private subprocess entry point for a single song's GPU processing."""

import argparse
import json
import os
from pathlib import Path
import sys


def process_song(audio_file: str, lyrics: str, language: str) -> dict[str, str]:
    # All model loading and native GPU initialization belongs to this process.
    from audio_processing.inference import split_audio
    from audio_processing.srt_process import word_to_sentence_level_srt
    from audio_processing.timestamps import generate_word_timestamps

    vocals_audio, instrumental_audio = split_audio(audio_file)
    word_level_srt = generate_word_timestamps(lyrics, vocals_audio, language=language)
    sentence_directory = Path("processing/sentence_level_srt")
    sentence_directory.mkdir(parents=True, exist_ok=True)
    sentence_level_srt = word_to_sentence_level_srt(
        srt_file_path=word_level_srt,
        lyrics=lyrics,
        output_file_path=str(sentence_directory / f"{Path(audio_file).stem}.srt"),
    )
    return {
        "vocals_audio": str(Path(vocals_audio).resolve()),
        "instrumental_audio": str(Path(instrumental_audio).resolve()),
        "word_level_srt": str(Path(word_level_srt).resolve()),
        "sentence_level_srt": str(Path(sentence_level_srt).resolve()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()
    request = json.load(sys.stdin)
    print(f"Starting song GPU worker (PID {os.getpid()})", flush=True)
    result = process_song(request["audio_file"], request["lyrics"], request["language"])
    args.result.write_text(json.dumps(result), encoding="utf-8")
    print(f"Song GPU worker finished (PID {os.getpid()})", flush=True)


if __name__ == "__main__":
    main()
