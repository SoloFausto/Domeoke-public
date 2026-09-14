from flask import Flask, abort
from flask import render_template, request, url_for
from flask_sock import Sock
from pathlib import Path


import downloaders.lyrics_api as lyrics_api
from audio_processing.pipeline import process_audio
from audio_processing.language import detect_lyrics_language
import msgpack


client_list = []


app = Flask("lyrics_downloader")
sock = Sock(app)
app.config['SOCK_SERVER_OPTIONS'] = {'ping_interval': 25}
with app.app_context():
    app.static_folder = 'static'
    app.static_url_path = '/static'

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404error.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500error.html'), 500

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/display")
def display():
    return render_template("display.html")

@app.route("/simple_page")
def custom_song():
    return render_template("simple_page.html")

@app.route("/youtube_page")
def pre_existing_song():
    return render_template("youtube_page.html")


@app.get("/query")
def query():
    request_args = request.args
    search = request_args.get("search", "")
    if not search:
        return render_template("simple_query_list.html", songs=[])
    song_suggestions = lyrics_api.fetch_song_choices(search)
    return render_template("simple_query_list.html", songs=song_suggestions) 

@app.get("/query_youtube")
def query_youtube():
    request_args = request.args
    search = request_args.get("search", "")
    if not search:
        return render_template("youtube_video_query.html", songs=[])
    song_suggestions = lyrics_api.suggest_youtube_videos(search)
    return render_template("youtube_video_query.html", songs=song_suggestions) 

@app.post("/process/<artist>/<song>")
def process(artist: str, song: str):
    try:
        app.logger.debug(f"Processing song: {artist} - {song} ")
        lyrics = lyrics_api.search_lyrics_ovh_api(artist=artist, song=song)
        print(lyrics)
        print(f"Fetched lyrics for {artist} - {song}:")
        if not lyrics:
            app.logger.error(f"Lyrics not found for {artist} - {song}")
            abort(404)  # This will trigger the 404 error handler
        lyrics = "\n".join([line for line in lyrics.splitlines() if line.strip()])
        detected_language = detect_lyrics_language(lyrics)
        app.logger.info("Detected language from lyrics: %s", detected_language)
        send_message("processing_notification")
        filename, youtube_id = lyrics_api.download_song_audio(artist, song)

        thumbnail_path = lyrics_api.download_youtube_thumbnail(youtube_id)
        
        audio_file = f"processing/input_audio/{filename}"
        
        processed = process_audio(audio_file, lyrics, detected_language)
        send_file(processed["instrumental_audio"], type="wavefile")
        send_file(processed["sentence_level_srt"], type="srtfile")
        send_file(thumbnail_path, type="pngfile")
        return "OK"
    
    except Exception as e:
        app.logger.error(f"Error processing song {artist} - {song}: {str(e)}")
        abort(500)  # This will trigger the 500 error handler

@app.post("/youtube_video/<video_id>")
def youtube_video(video_id: str):
    try:
        app.logger.debug(f"Processing YouTube video: {video_id}")
        filename = lyrics_api.download_youtube_video(video_id)
        url_for(endpoint='static', filename=filename)
        send_message("youtube_video")
        return "OK"
    except Exception as e:
        app.logger.error(f"Error processing YouTube video {video_id}: {str(e)}")
        abort(500)  # This will trigger the 500 error handler

@sock.route('/webSockets')
def echo(ws):
    client_list.append(ws)
    try:
        while ws.receive() is not None:
            pass
    finally:
        if ws in client_list:
            client_list.remove(ws)



def send_file(filepath: str,type: str):
    clients = client_list.copy()
    data = Path(filepath).read_bytes()
    msg = {
        "type": type,
        "filename": Path(filepath).name,
        "payload": data,
    }
    packed = msgpack.packb(msg, use_bin_type=True)
    print(clients)
    for client in clients:
        try:
            client.send(packed)
        except: 
            if client in client_list:
                client_list.remove(client)


def send_message(message: str):
    clients = client_list.copy()
    msg = {
        "type": message,
        "filename": "",
        "payload": "",
    }
    packed = msgpack.packb(msg, use_bin_type=True)
    print(clients)
    for client in clients:
        try:
            client.send(packed)
        except: 
            if client in client_list:
                client_list.remove(client)