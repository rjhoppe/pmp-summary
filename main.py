import json
from youtube_search import YoutubeSearch
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from mistralai import Mistral
import tiktoken
from dotenv import load_dotenv
import os
import sys
import time

load_dotenv()

api_key = os.environ["MISTRAL_API_KEY"]
model = "mistral-small-latest"

client = Mistral(api_key=api_key)

## Get Video ID
def get_video_id():
  print("Geting the most recent stream's video id...")
  max_results = 5
  search_json = YoutubeSearch('PreMarket Prep', max_results=max_results).to_json()
  print(search_json)
  search = json.loads(search_json)
  i = 0
  video_id = ''
  while i < max_results and video_id == '':
    if search['videos'][i]['channel'] != 'PreMarket Prep':
      i += 1
    else:
      video_id = search['videos'][0]['id']
      print(search['videos'][i]['title'])
      print(search['videos'][i]['publish_time'])
  return video_id

## Get Captions
def get_captions(video_id: str):
  # try except here to catch weird "video not available error"
  print("Extracting captions...")
  captions = YouTubeTranscriptApi.get_transcript(video_id)
  formatter = TextFormatter()
  fmt_captions = formatter.format_transcript(captions)
  return fmt_captions

def chunk_text(text, max_tokens=2048, overlap=100):
    print("Chunking text...")

    # Use tiktoken encoder (OpenAI encoding as approximation)
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    tokens = encoding.encode(text)

    print(f"Total tokens: {len(tokens)}")

    # Prevent invalid settings
    if overlap >= max_tokens:
        raise ValueError("Overlap must be smaller than max_tokens.")

    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk = encoding.decode(chunk_tokens)
        chunks.append(chunk)

        # Move forward
        start += max_tokens - overlap

    print(f"Chunks created: {len(chunks)}")
    return chunks

def summarize_chunks(chunks):
    print("Summarizing chunks...")
    summaries = []
    try:
      for chunk in chunks:
        request = [{"role":"user", "content":f"Summarize this text:\n\n{chunk}"}]
        response = client.chat.complete(model=model, messages=request)
        summaries.append(response.choices[0].message.content)
    
    except Exception as e:
       print(e)
       return []
    
    return summaries

# def send_to_ntfy():
#    return

# def clean_up_output():
#    return

# def delete_local_file(filename):
#   print(f"Deleting {filename}...")
#   cwd = os.getcwd()
#   filepath = os.path.join(cwd + "/" + filename)
#   os.remove(filepath)


## Refactor into class
def main():
  start_time = time.time()
  video_id = get_video_id()
  text = get_captions(video_id)

  chunks = chunk_text(text)
  summaries = summarize_chunks(chunks)

  final_summary = "\n".join(summaries)
  print("Saving summaries output to file...")
  with open("summary_output.txt", "w", encoding="utf-8") as f:
    f.write(final_summary)
  
  # delete_local_file("summary.txt")

  end_time = time.time()
  execution_time = end_time - start_time
  print(f"Execution time: {execution_time:.6f} seconds")

if __name__ == "__main__":
  main()