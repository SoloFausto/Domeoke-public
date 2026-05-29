import srt

def word_to_sentence_level_srt(srt_file_path, lyrics, output_file_path):
    """
    Processes an SRT file and a TXT file to generate a new SRT file with lyrics.

    Args:
        srt_file_path (str): Path to the input SRT file.
        txt_file_path (str): Path to the input TXT file containing lyrics.
        output_file_path (str): Path to save the generated SRT file.
    """
    with open(srt_file_path, 'r', encoding='utf-8') as f:
        subs_file = f.read()
    
    subs = list(srt.parse(subs_file))

    start_end_words = []
    i = 1
    for line in lyrics.splitlines():
        wordlist = line.split()
        start_end_words.append((i, i + len(wordlist) - 1))
        i += len(wordlist)

    lyrics_lines = []
    for start_word, end_word in start_end_words:
        line = [subs[j] for j in range(start_word - 1, end_word)]
        lyrics_lines.append(line)

    subtitles = []
    for line in lyrics_lines:
        line_content = ' '.join([sub.content for sub in line])
        start_time = line[0].start
        end_time = line[-1].end
        subtitles.append(srt.Subtitle(index=line[0].index, start=start_time, end=end_time, content=line_content))

    composed_subs = srt.compose(subtitles)
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(composed_subs)
    
    return output_file_path

# Example usage:
# word_to_sentence_level_srt('Carinio_word_timestamps.srt', 'base_lyrics/carinio.txt', 'Carinio_lyrics.srt')