import requests 
import json
import time
import random
import urllib.request
from ytmusicapi import YTMusic
from pytubefix import YouTube, Search


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
    yt = YouTube(f'http://youtube.com/watch?v={yt_id}')
    ys = yt.streams.get_audio_only()
    ys.download(output_path='processing/input_audio')
    return [ys.default_filename, yt_id]

def download_youtube_video(id: str):
    yt = YouTube(f'http://youtube.com/watch?v={id}')
    ys = yt.streams.get_highest_resolution()
    ys.download(output_path='static',filename="video.mp4")
    return ys.default_filename

def download_youtube_thumbnail(id: str):
    thumbnail_url = f'https://img.youtube.com/vi/{id}/maxresdefault.jpg'
    filename = f'processing/thumbnails/{id}.jpg'
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
    results = Search(query)
    video_choices = list()

    for video in results.videos:
        watchid = video.watch_url.replace('https://youtube.com/watch?v=', '')
        video_choices.append({
            'title': video.title,
            'watch_url': watchid,
            'length': video.length,
            'thumbnail': video.thumbnail_url,
            'author': video.author,
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