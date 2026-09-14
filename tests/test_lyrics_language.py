from concurrent.futures import ThreadPoolExecutor
import unittest

from audio_processing.language import detect_lyrics_language


class LyricsLanguageTests(unittest.TestCase):
    def test_nonlinguistic_input_is_not_silently_assigned_english(self):
        with self.assertRaises(ValueError):
            detect_lyrics_language(" \n12345 -- !!!")

    def test_chinese_script_variants_use_whispers_single_language_code(self):
        simplified = "夜晚的天空有很多星星，我想和你一起走到远方。无论明天会发生什么，我都会一直陪在你的身边。"
        traditional = "夜晚的天空有很多星星，我想和你一起走到遠方。無論明天會發生什麼，我都會一直陪在你的身邊。"
        self.assertEqual(detect_lyrics_language(simplified), "zh")
        self.assertEqual(detect_lyrics_language(traditional), "zh")

    def test_ambiguous_text_is_repeatable_across_concurrent_requests(self):
        lyrics = "Otec matka syn."
        expected = detect_lyrics_language(lyrics)
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(detect_lyrics_language, [lyrics] * 12))
        self.assertEqual(results, [expected] * 12)
