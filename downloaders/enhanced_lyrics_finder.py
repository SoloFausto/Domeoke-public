#!/usr/bin/env python3
"""
Enhanced Lyrics Finder

This script uses multiple public APIs and web sources to retrieve song lyrics,
with robust fallback mechanisms and formatting options.
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import sys
import time
import random
from urllib.parse import quote, urljoin

class LyricsFinder:
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        # List of lyrics sources to try
        self.sources = [
            {
                'name': 'lyrics.ovh API',
                'search_function': self._search_lyrics_ovh_api
            },
            {
                'name': 'lyrics.ovh Web',
                'search_function': self._search_lyrics_ovh_web
            },
            {
                'name': 'AZLyrics',
                'search_function': self._search_azlyrics
            },
            {
                'name': 'Genius',
                'search_function': self._search_genius
            },
            {
                'name': 'LyricsFreak',
                'search_function': self._search_lyricsfreak
            }
        ]
    
    def log(self, message):
        """Print log messages if verbose mode is enabled"""
        if self.verbose:
            print(message)
    
    def _make_request(self, url, timeout=10):
        """Make a request with headers to avoid bot detection"""
        try:
            # Random delay between requests
            time.sleep(random.uniform(0.5, 1.5))
            self.log(f"Requesting URL: {url}")
            response = requests.get(url, headers=self.headers, timeout=timeout)
            if response.status_code == 200:
                return response
            else:
                self.log(f"Request failed with status code: {response.status_code}")
        except Exception as e:
            self.log(f"Error making request to {url}: {e}")
        return None
    
    def _search_lyrics_ovh_api(self, artist, title):
        """Search for lyrics using lyrics.ovh API"""
        try:
            self.log(f"Searching lyrics.ovh API for '{title}' by '{artist}'")
            url = f"https://api.lyrics.ovh/v1/{quote(artist)}/{quote(title)}"
            response = self._make_request(url)
            
            if response and response.status_code == 200:
                try:
                    data = response.json()
                    if 'lyrics' in data and data['lyrics']:
                        # Print the raw lyrics for debugging
                        if self.verbose:
                            raw_lyrics = data['lyrics']
                            self.log(f"Raw lyrics from API (first 100 chars):")
                            self.log(repr(raw_lyrics[:100]))
                        return data['lyrics']
                except json.JSONDecodeError:
                    self.log("Failed to parse JSON response from lyrics.ovh API")
            elif response and response.status_code == 404:
                self.log("Lyrics not found on lyrics.ovh API")
        except Exception as e:
            self.log(f"Error with lyrics.ovh API: {e}")
        
        return None
    
    def _search_lyrics_ovh_web(self, artist, title):
        """Search for lyrics using lyrics.ovh website"""
        try:
            self.log(f"Searching lyrics.ovh website for '{title}' by '{artist}'")
            search_url = f"https://lyrics.ovh/search?q={quote(artist)}+{quote(title)}"
            response = self._make_request(search_url)
            
            if response and response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find search results
                results = soup.select('ul.results li a')
                if results:
                    # Get the first result URL
                    result_url = results[0].get('href')
                    if result_url:
                        # Make sure it's an absolute URL
                        if not result_url.startswith('http'):
                            result_url = urljoin('https://lyrics.ovh/', result_url)
                        
                        # Get the lyrics page
                        lyrics_response = self._make_request(result_url)
                        if lyrics_response and lyrics_response.status_code == 200:
                            lyrics_soup = BeautifulSoup(lyrics_response.text, 'html.parser')
                            lyrics_div = lyrics_soup.select_one('div.lyrics')
                            if lyrics_div:
                                return lyrics_div.get_text()
        except Exception as e:
            self.log(f"Error with lyrics.ovh website: {e}")
        
        return None
    
    def _search_azlyrics(self, artist, title):
        """Search for lyrics on AZLyrics"""
        try:
            self.log(f"Searching AZLyrics for '{title}' by '{artist}'")
            
            # Format the search query for AZLyrics URL structure
            artist_formatted = artist.lower().replace(' ', '')
            title_formatted = title.lower().replace(' ', '')
            
            # Try direct URL first (AZLyrics has a predictable URL structure)
            direct_url = f"https://www.azlyrics.com/lyrics/{artist_formatted}/{title_formatted}.html"
            response = self._make_request(direct_url)
            
            if response and response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # AZLyrics typically has lyrics in a div with no class after a div with class 'ringtone'
                ringtone_div = soup.find('div', class_='ringtone')
                if ringtone_div:
                    lyrics_div = ringtone_div.find_next_sibling('div')
                    if lyrics_div and not lyrics_div.get('class'):
                        return lyrics_div.get_text()
            
            # If direct URL fails, try search
            search_url = f"https://search.azlyrics.com/search.php?q={quote(artist)}+{quote(title)}"
            search_response = self._make_request(search_url)
            
            if search_response and search_response.status_code == 200:
                search_soup = BeautifulSoup(search_response.text, 'html.parser')
                
                # Find search results
                results = search_soup.select('td.visitedlyr a')
                if results:
                    # Get the first result URL
                    result_url = results[0].get('href')
                    if result_url:
                        # Get the lyrics page
                        lyrics_response = self._make_request(result_url)
                        if lyrics_response and lyrics_response.status_code == 200:
                            lyrics_soup = BeautifulSoup(lyrics_response.text, 'html.parser')
                            ringtone_div = lyrics_soup.find('div', class_='ringtone')
                            if ringtone_div:
                                lyrics_div = ringtone_div.find_next_sibling('div')
                                if lyrics_div and not lyrics_div.get('class'):
                                    return lyrics_div.get_text()
        except Exception as e:
            self.log(f"Error with AZLyrics: {e}")
        
        return None
    
    def _search_genius(self, artist, title):
        """Search for lyrics on Genius"""
        try:
            self.log(f"Searching Genius for '{title}' by '{artist}'")
            search_url = f"https://genius.com/search?q={quote(artist)}+{quote(title)}"
            response = self._make_request(search_url)
            
            if response and response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find search results
                results = soup.select('ul.search_results li a')
                if results:
                    # Get the first result URL
                    result_url = results[0].get('href')
                    if result_url:
                        # Get the lyrics page
                        lyrics_response = self._make_request(result_url)
                        if lyrics_response and lyrics_response.status_code == 200:
                            lyrics_soup = BeautifulSoup(lyrics_response.text, 'html.parser')
                            lyrics_divs = lyrics_soup.select('div[data-lyrics-container="true"]')
                            if lyrics_divs:
                                lyrics = []
                                for div in lyrics_divs:
                                    lyrics.append(div.get_text())
                                return '\n'.join(lyrics)
        except Exception as e:
            self.log(f"Error with Genius: {e}")
        
        return None
    
    def _search_lyricsfreak(self, artist, title):
        """Search for lyrics on LyricsFreak"""
        try:
            self.log(f"Searching LyricsFreak for '{title}' by '{artist}'")
            search_url = f"https://www.lyricsfreak.com/search.php?q={quote(artist)}+{quote(title)}"
            response = self._make_request(search_url)
            
            if response and response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find search results
                results = soup.select('.song-list a')
                if results:
                    # Get the first result URL
                    result_url = results[0].get('href')
                    if result_url:
                        # Make sure it's an absolute URL
                        if not result_url.startswith('http'):
                            result_url = urljoin('https://www.lyricsfreak.com/', result_url)
                        
                        # Get the lyrics page
                        lyrics_response = self._make_request(result_url)
                        if lyrics_response and lyrics_response.status_code == 200:
                            lyrics_soup = BeautifulSoup(lyrics_response.text, 'html.parser')
                            lyrics_div = lyrics_soup.select_one('div#content')
                            if lyrics_div:
                                return lyrics_div.get_text()
        except Exception as e:
            self.log(f"Error with LyricsFreak: {e}")
        
        return None
    
    def _clean_lyrics(self, lyrics):
        """Clean lyrics by removing headers and optionally line breaks"""
        if not lyrics:
            return None
            
        # Print the raw lyrics for debugging
        if self.verbose:
            self.log(f"Raw lyrics (first 100 chars):")
            self.log(repr(lyrics[:100]))
            
            # Check for any special characters at the beginning
            if lyrics and len(lyrics) > 0:
                first_few_chars = lyrics[:10]
                char_codes = [ord(c) for c in first_few_chars]
                self.log(f"First few character codes: {char_codes}")
        
        # IMPORTANT: Preserve the original lyrics before any cleaning
        original_lyrics = lyrics
        
        # Pattern to match section headers like [Verse 1], [Chorus], etc.
        header_pattern = r'\[(Verse|Chorus|Bridge|Intro|Outro|Pre-Chorus|Hook|Refrain|Interlude).*?\]'
        cleaned_lyrics = re.sub(header_pattern, '', original_lyrics)
        
        # Remove common API footers
        cleaned_lyrics = re.sub(r'This Lyrics is NOT for Commercial use.*', '', cleaned_lyrics, flags=re.DOTALL)
        
        # Final cleanup: trim any leading/trailing whitespace
        cleaned_lyrics = cleaned_lyrics.strip()
        
        # Print the cleaned lyrics for debugging
        if self.verbose:
            self.log(f"Cleaned lyrics (first 100 chars):")
            self.log(repr(cleaned_lyrics[:100]))
            
        return cleaned_lyrics
    
    def get_lyrics(self, title, artist=None):
        """Main function to get lyrics for any song"""
        if not artist:
            # Try to extract artist from title if not provided
            parts = title.split(' - ', 1)
            if len(parts) == 2:
                artist, title = parts
                self.log(f"Extracted artist '{artist}' and title '{title}'")
        
        # If we still don't have an artist, use a generic placeholder
        if not artist:
            self.log("No artist specified, search results may be less accurate")
            artist = "Unknown"
        
        self.log(f"Searching for lyrics: '{title}' by '{artist}'")
        
        # Try each source
        for source in self.sources:
            self.log(f"Trying {source['name']}...")
            lyrics = source['search_function'](artist, title)
            
            if lyrics:
                cleaned_lyrics = self._clean_lyrics(lyrics)
                
                if cleaned_lyrics:
                    self.log(f"Successfully retrieved lyrics from {source['name']}")
                    return cleaned_lyrics
        
        self.log("Failed to find lyrics from all sources.")
        
        # Fallback to a simple web search suggestion
        self.log("\nSuggestion: Try searching for the lyrics manually using:")
        self.log(f"  https://www.google.com/search?q={quote(artist)}+{quote(title)}+lyrics")
        
        return None

def save_lyrics_to_file(lyrics, filename=None):
    """Save the lyrics to a text file"""
    if not lyrics:
        print("No lyrics to save.")
        return False
    
    if not filename:
        filename = "lyrics.txt"
    
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(lyrics)
        print(f"Lyrics saved to {filename}")
        return True
    except Exception as e:
        print(f"Error saving lyrics to file: {e}")
        return False

def interactive_mode():
    """Run the lyrics finder in interactive mode"""
    print("=== Enhanced Lyrics Finder ===")
    print("Enter song information to search for lyrics")
    
    while True:
        # Get song title
        title_input = input("\nSong title (or 'quit' to exit): ").strip()
        if title_input.lower() == 'quit':
            break
        
        if not title_input:
            print("Song title cannot be empty. Please try again.")
            continue
        
        # Get artist (optional)
        artist = input("Artist (optional): ").strip()
        
        # Get output filename (optional)
        default_filename = f"{title_input.lower().replace(' ', '_')}_lyrics.txt"
        filename_input = input(f"Output filename (default: {default_filename}): ").strip()
        filename = filename_input if filename_input else default_filename
        
        
        # Create finder and search for lyrics
        print("\nSearching for lyrics... (this may take a moment)")
        finder = LyricsFinder(verbose=True)
        lyrics = finder.get_lyrics(title_input, artist if artist else None)
        
        if lyrics:
            print("\n=== Lyrics Found ===")
            print(lyrics)
            print("\n===================")
            
            # Ask to save
            save_choice = input("\nSave lyrics to file? (y/n): ").strip().lower()
            if save_choice == 'y':
                save_lyrics_to_file(lyrics, filename)
        else:
            print("\nNo lyrics found through any sources.")
            print("Please try a different song or check the spelling.")

def main():
    """Main function to run the lyrics finder"""
    if len(sys.argv) > 1:
        # Command-line mode
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print("Usage:")
            print("  python lyrics_finder.py                      # Run in interactive mode")
            print("  python lyrics_finder.py \"Song Title\"         # Search for a specific song")
            print("  python lyrics_finder.py \"Song Title\" \"Artist\" # Search with artist name")
            print("  python lyrics_finder.py \"Song Title\" \"Artist\" --keep-linebreaks # Keep line breaks in lyrics")
            print("  python lyrics_finder.py \"Song Title\" \"Artist\" --debug # Show detailed debugging info")
            return
        
        title = sys.argv[1]
        artist = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
        
        # Check for options
        remove_linebreaks = True
        verbose = False
        
        if '--keep-linebreaks' in sys.argv:
            remove_linebreaks = False
        if '--debug' in sys.argv:
            verbose = True
        
        finder = LyricsFinder(verbose=verbose, remove_linebreaks=remove_linebreaks)
        lyrics = finder.get_lyrics(title, artist)
        
        if lyrics:
            print("\n=== Lyrics ===")
            print(lyrics)
            
            # Default filename
            default_filename = f"{title.lower().replace(' ', '_')}_lyrics.txt"
            save_lyrics_to_file(lyrics, default_filename)
        else:
            print("No lyrics found through any sources.")
            print("Please try a different song or check the spelling.")
    else:
        # Interactive mode
        interactive_mode()

if __name__ == "__main__":
    main()
