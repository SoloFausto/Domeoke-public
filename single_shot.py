
import downloaders.lyrics_api as lyrics_api
from audio_processing.pipeline import process_audio
from audio_processing.language import detect_lyrics_language

artist = ""
song = ""

def fetch_lyrics_and_audio(artist, song):
    lyrics = lyrics_api.search_lyrics_ovh_api(artist=artist, song=song)
    print(lyrics)
    print(f"Fetched lyrics for {artist} - {song}:")
    if not lyrics:
        return

    lyrics = "\n".join([line for line in lyrics.splitlines() if line.strip()])
    detected_language = detect_lyrics_language(lyrics)
    print(f"Detected language from lyrics: {detected_language}")
    filename, youtube_id = lyrics_api.download_song_audio(artist, song)

    thumbnail_path = lyrics_api.download_youtube_thumbnail(youtube_id)

    audio_file = f"processing/input_audio/{filename}"

    processed = process_audio(audio_file, lyrics, detected_language)
    print(f"Generated audio and subtitles: {processed}")

fetch_lyrics_and_audio(artist, song)