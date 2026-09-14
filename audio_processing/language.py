"""Identify the predominant language of lyrics without loading an audio model."""

from langdetect import DetectorFactory, LangDetectException
from langdetect.detector_factory import PROFILES_DIRECTORY


_factory = DetectorFactory()
_factory.load_profile(PROFILES_DIRECTORY)
_factory.seed = 0


def detect_lyrics_language(lyrics: str) -> str:
    """Return a Whisper-compatible language code, or reject undetectable text."""
    # Each request gets its own detector and seeded random state; profiles are shared.
    detector = _factory.create()
    detector.append(lyrics)
    try:
        language = detector.detect()
    except LangDetectException as error:
        raise ValueError("Cannot determine a language from these lyrics; meaningful text is required.") from error
    # langdetect distinguishes Chinese scripts; Whisper uses a single language code.
    return "zh" if language in ("zh-cn", "zh-tw") else language
