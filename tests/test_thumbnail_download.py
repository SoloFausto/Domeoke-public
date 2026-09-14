import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

from downloaders.lyrics_api import download_youtube_thumbnail


class ThumbnailDownloadTests(unittest.TestCase):
    def test_download_creates_missing_directories_and_can_repeat(self):
        retrieve = urllib.request.urlretrieve
        previous_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.jpg"
            source.write_bytes(b"thumbnail contents")
            try:
                os.chdir(directory)
                # Use urllib's real file transfer without depending on YouTube.
                with patch("downloaders.lyrics_api.urllib.request.urlretrieve",
                           side_effect=lambda url, filename: retrieve(source.as_uri(), filename)):
                    downloaded = Path(download_youtube_thumbnail("example"))
                    self.assertEqual(downloaded.read_bytes(), source.read_bytes())
                    source.write_bytes(b"updated thumbnail")
                    downloaded = Path(download_youtube_thumbnail("example"))
                    self.assertEqual(downloaded.read_bytes(), source.read_bytes())
            finally:
                os.chdir(previous_directory)
