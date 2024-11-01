import json
from youtube_search import YoutubeSearch
import yt_dlp
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

  video_link = f"https://www.youtube.com/watch?v={video_id}"
  return video_link

## Get Audio
# desired output -> pmp.mp3
def get_audio(video_link: str):
  print("Extracting audio from video..")
  output_name = "pmp.mp3"
  # get_audio_cmd = f"yt-dlp -x --audio-format mp3 -o {output_name} {video_id}"
  get_audio_cmd = f"yt-dlp -x --audio-format mp3 {video_link}"
  audio_result = subprocess.run(get_audio_cmd, shell=True, capture_output=True, text=True)
  if audio_result.returncode != 0:
    print("An error occurred:", audio_result.stderr)
  else:
    print("Output:\n", audio_result.stdout)

  print("Renaming audio file...")
  pattern = r'\b[\w\-. ]+\.mp3\b'
  for filename in os.listdir(os.getcwd()):
    if re.match(pattern, filename, re.IGNORECASE):
      os.rename(filename, "pmp.mp3")

  ## Get Transcription
def get_transcription():
  print("Beginning transcription process..")
  cwd = os.getcwd()
  audio_file = "pmp.mp3"
  audio_path = os.path.join(cwd, audio_file)
  transcript_path = os.path.join(cwd, "transcript.txt")
  get_transcription_cmd = ["whisper", audio_file, "--model", "medium"]
  # Open a file to write the output
  with open(transcript_path, "w") as output:
    # Run the command and redirect output to the file
    trans_result = subprocess.run(get_transcription_cmd, stdout=output, stderr=subprocess.STDOUT, check=True)

  if trans_result.returncode == 0:
    print("Transcription stored in transcript.txt")
  else:
    print("An error occurred processing the transcription")

## Send Transcription to Ollama
def summarize_transcription():
  cwd = os.getcwd()
  summary_path = os.path.join(cwd, "summary.txt")
  prompt = ""
  summarize_cmd = "" 
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
  # get_audio(video_id)
  get_transcription()
  # summarize_transcription()
  # clean_up()

if __name__ == "__main__":
  main()