import json
from youtube_search import YoutubeSearch
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import subprocess
import os
import re

## Get Video ID
def get_video_id():
  print("Geting the most recent stream's video id...")
  max_results = 3
  search_json = YoutubeSearch('PreMarket Prep', max_results=max_results).to_json()
  search = json.loads(search_json)
  i = 0
  video_id = ''
  while i < max_results and video_id == '':
    if search['videos'][i]['channel'] != 'Benzinga':
      i += 1
    else:
      video_id = search['videos'][i]['id']

  return video_id


## Get Captions
def get_captions(video_id: str):
  print("Extracting captions...")
  captions = YouTubeTranscriptApi.get_transcript(video_id)
  formatter = TextFormatter()
  fmt_captions = formatter.format_transcript(captions)

  with open('summary.txt', 'w', encoding='utf-8') as file:
    file.write(fmt_captions)

## Send Captions to Ollama
def summarize_captions():
  print("Passing summary.txt to ollama...")
  cwd = os.getcwd()
  output_path = os.path.join(cwd, "summary.txt")
  prompt = "summarize the stock market commentary provided"
  summarize_cmd = ["ollama", "run", "mistral", prompt]
  with open(summary_path, "w") as output:
    # Run the command and redirect output to the file
    sum_result = subprocess.run(summarize_cmd, stdout=output, stderr=subprocess.STDOUT)  

  if sum_result.returncode == 0:
    print("Transcription stored in transcript.txt")
  else:
    print("An error occurred processing the transcription")

def clean_up():
  # remove all files except summary output
  return

# Refactor into class
def main():
  video_id = get_video_id()
  get_captions(video_id)
  summarize_transcription()
  # clean_up()

if __name__ == "__main__":
  main()