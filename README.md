# Domeoke
## Custom Karaoke Software for domes

### General Description:
Domeoke is a fully featured software to play Karaoke songs in a dome. Through a simple user interface, a user can connect into the server and select any song that they want to sing.
Currently there are two sources where a user can get their songs from; firstly, Domeoke can download and display any karaoke video from Youtube making it possible to sing a wide variety of songs that are already made by other people.
Secondly, Domeoke can also generate its own karaoke versions of most songs through a custom audio pipeline that runs whenever a song is requested. 

 After a user selects a Youtube version or generates a custom Karaoke version, the server notifies all connected display frontends to begin displaying the karaoke song. 
 This websocket connection makes it possible to have different implementations of the actual program that displays the lyrics, where for example a Unity and Unreal frontend can be both connected to the same server.
 
### Technical Specification:
The Domeoke server is primarily a Flask server that hosts a website from where the clients can browse and select songs. It also keeps an active connection with all the clients where it sends the finished instrumentals and lyrics.

The custom audio pipeline consists of a few steps: 
1. Fetch the lyrics
2. Detect the predominant language from the lyrics text
3. Download the studio audio and separate the vocals from the instrumental
4. Force align the lyrics with the song, generating a word by word timestamps of where each word is situated in the lyrics
5. Join these word level timestamps to make full sentences again
This pipeline has a couple shortcomings that make it not really able to be used in every situation: Firstly, for a requested song there might not be lyrics available for it; secondly, the forced alignment that we do is suceptible to fail in situations where a song features more than one language or the singing isn't quite clear.
That is why the standard Youtube version is meant to suplement these shortcomings so that a user can sing most songs.

Between the server and the display frontend we use Message Pack to send the finished files, sending the audio data in a .wav file, lyrics in an .srt, and a cover image in a .png format.

We also run a node server to fetch the lyrics, this server exposes a rest interface that lets the Flask frontend get the lyrics from a javascript library.

### Browser display
Open `http://<server>:5000/display` (or **Open karaoke display** on the home page) before requesting a song. Keep it open on the screen used for singing, and use **Choose a song** to open the generated-song selector in another tab. Other devices can use the same server address.

The display connects to `/webSockets` on the same host, receives MessagePack WAV/SRT/PNG broadcasts, and plays the instrumental with synchronized current, previous, and upcoming lyric lines. Playback controls provide pause, seeking, and volume; **Fullscreen** expands the stage. If autoplay is blocked, press Play once the song is ready.

### TODO:
- Research what Nvidia has with Forced aligment: https://research.nvidia.com/labs/conv-ai/blogs/2023/2023-08-forced-alignment/#formulating-the-problem
- Better error handling from the server side in regards to notifying the user
- There is a bug with regards to the audio splitting model where it locks up and the server needs to be manually restarted.
- Improve the lyrics scraping library.
- Improve code quality and organization.
- Implement media controls from the user side.
- Implement loading notifications for the user (either we can implement it so that the loading shows up in the dome or in the web; I think that the former is more viable)
- Implement song caching/ manage what files are currently in the server.


### Credits:
**Main Programmers:**
Fausto De Leon (Lead programmer),
Yibo (Kendall) Wang (Frontend Programmer)

**Aditional Advising:**
Joseph Eakin 

**First iteration done over the summer break of 2025**

**Used Libraries:**
Domeoke's custom audio pipeline and other functionality could not work without these libraries:

- Flask (Licenced under BSD 3-Clause "New" or "Revised" License)
- langdetect (Licensed under Apache License 2.0)
- Lyrics.ovh (Licenced under GNU General Public License v3.0)
- alltomp3 (Licenced under GNU Affero General Public License v3.0)
- yt-dlp (Unlicense)
- ytmusicapi (Licenced under MIT Licence)
- Music-Source-Separation-Training (Licenced under MIT Licence)
- stable-ts (Licenced under MIT Licence)
- srt (Licenced under MIT Licence)
- flask-sock (Licenced under MIT Licence)
- melbandroformer_instvoc_duality_v2 model from user pcunwa in Hugging Face
