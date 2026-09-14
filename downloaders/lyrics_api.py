import requests 
import json
import time
import random
import urllib.request
from ytmusicapi import YTMusic
from pathlib import Path
from yt_dlp import YoutubeDL


def fetch_song_choices(query: str):
    song_choices = list()
    response = requests.get(f"https://api.lyrics.ovh/suggest/{query}")
    
    if response.status_code == 200:
        json_object = json.loads(response.text)
        for song in json_object['data']:
            song_choices.append({
                'title': song['title'],
                'artist': song['artist']['name'],
                'album': song['album']['title'],
                'cover': song['album']['cover'],
            })
    return song_choices

def download_song_audio(artist: str,song: str, song_index: int = 0):
    query = f"{artist} - {song}"

    ytmusic = YTMusic()
    yt_id = ytmusic.search(query, filter="songs")[song_index]['videoId']
    options = {
        "format": "bestaudio/best",
        "outtmpl": "processing/input_audio/%(id)s.%(ext)s",
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }
    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(f"https://www.youtube.com/watch?v={yt_id}", download=True)
        filename = Path(downloader.prepare_filename(info)).with_suffix(".mp3").name
    return [filename, yt_id]

def download_youtube_video(id: str):
    options = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
        "merge_output_format": "mp4",
        "outtmpl": "static/video.%(ext)s",
        "noplaylist": True,
        "overwrites": True,
    }
    with YoutubeDL(options) as downloader:
        downloader.extract_info(f"https://www.youtube.com/watch?v={id}", download=True)
    return "video.mp4"

def download_youtube_thumbnail(id: str):
    thumbnail_url = f'https://img.youtube.com/vi/{id}/maxresdefault.jpg'
    filename = f'processing/thumbnails/{id}.jpg'
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(thumbnail_url, filename)
    return filename

def make_request(url, timeout=10):
    """Make a request with headers to avoid bot detection"""
    headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
    try:
        # Random delay between requests
        time.sleep(random.uniform(0.5, 1.5))
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            return response
    except Exception as e:
        print(f"Error making request to {url}: {e}")
    return None

def suggest_youtube_videos(query: str):
    options = {"extract_flat": "in_playlist", "skip_download": True}
    with YoutubeDL(options) as downloader:
        results = downloader.extract_info(f"ytsearch20:{query}", download=False)
    video_choices = []
    for video in results.get("entries", []):
        if not video or not video.get("id"):
            continue
        thumbnails = video.get("thumbnails") or []
        video_choices.append({
            "title": video.get("title") or video["id"],
            "watch_url": video["id"],
            "length": video.get("duration"),
            "thumbnail": thumbnails[-1]["url"] if thumbnails else "",
            "author": video.get("channel") or video.get("uploader") or "",
        })
    return video_choices


def search_lyrics_ovh_api(artist, song):
    """Search for lyrics using lyrics.ovh API"""
    try:
        url = f"https://api.lyrics.ovh/v1/{artist}/{song}"
        response = make_request(url)
        if response and response.status_code == 200:
            try:
                data = response.json()
                if 'lyrics' in data and data['lyrics']:
                    # Print the raw lyrics for debugging
                    return data['lyrics']
            except json.JSONDecodeError:
                print("Error decoding JSON response from lyrics.ovh API")
        elif response and response.status_code == 404:
            print(f"Lyrics not found for {artist} - {song}")
    except Exception as e:
        print(f"Error searching lyrics for {artist} - {song}: {e}")
    
    return None