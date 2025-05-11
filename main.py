import datetime
import json
from youtube_search import YoutubeSearch
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from mistralai import Mistral
import tiktoken
from dotenv import load_dotenv
import os
import time
import requests
from typing import List, Optional

load_dotenv()

default_api_key = os.environ.get("MISTRAL_API_KEY")
default_model = "mistral-small-latest"
default_wastebin_url = os.environ.get("WASTEBIN_URL")
default_ntfy_url = os.environ.get("NTFY_URL")

class PreMarketPrepSummarizer:
    """
    Summarizes the most recent 'PreMarket Prep' YouTube stream using Mistral API.
    """
    def __init__(self, api_key: Optional[str] = None, model: str = default_model, wastebin_url: str = default_wastebin_url, summary_url: str = default_wastebin_url):
        self.api_key = api_key or default_api_key
        self.model = model
        self.client = Mistral(api_key=self.api_key)
        self.wastebin_url = wastebin_url
        self.summary_url = summary_url

    def get_video_id(self, channel_name: str = 'PreMarket Prep', max_results: int = 5) -> str:
        """
        Get the most recent video ID from the specified channel.
        """
        print("Getting the most recent stream's video id...")
        search_json = YoutubeSearch(channel_name, max_results=max_results).to_json()
        search = json.loads(search_json)
        for i in range(max_results):
            if search['videos'][i]['channel'] == channel_name:
                print(search['videos'][i]['title'])
                print(search['videos'][i]['publish_time'])
                return search['videos'][i]['id']
        raise ValueError(f"No video found for channel {channel_name}")

    def get_captions(self, video_id: str) -> str:
        """
        Extract captions from a YouTube video by ID.
        """
        print("Extracting captions...")
        captions = YouTubeTranscriptApi.get_transcript(video_id)
        formatter = TextFormatter()
        fmt_captions = formatter.format_transcript(captions)
        return fmt_captions

    def chunk_text(self, text: str, max_tokens: int = 2048, overlap: int = 100) -> List[str]:
        """
        Chunk text into pieces of up to max_tokens, with overlap.
        """
        print("Chunking text...")
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        tokens = encoding.encode(text)
        print(f"Total tokens: {len(tokens)}")
        if overlap >= max_tokens:
            raise ValueError("Overlap must be smaller than max_tokens.")
        chunks = []
        start = 0
        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk = encoding.decode(chunk_tokens)
            chunks.append(chunk)
            start += max_tokens - overlap
        print(f"Chunks created: {len(chunks)}")
        return chunks

    def summarize_chunks(self, chunks: List[str]) -> List[str]:
        """
        Summarize each chunk using the Mistral API.
        """
        print("Summarizing chunks...")
        summaries = []
        for chunk in chunks:
            try:
                request = [{"role": "user", "content": f"Summarize this text:\n\n{chunk}"}]
                response = self.client.chat.complete(model=self.model, messages=request)
                summaries.append(response.choices[0].message.content)
            except Exception as e:
                print(f"Error summarizing chunk: {e}")
                summaries.append("")
        return summaries

    def save_summary(self, summary: str, filename: str = "summary_output.txt") -> None:
        """
        Save the summary to a file. For testing purposes only.
        """
        print(f"Saving summaries output to {filename}...")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(summary)

    def send_to_wastebin(
        self,
        summary: str,
        extension: str = None,
        title: str = None,
        expires: int = None,
        burn_after_reading: bool = None,
        password: str = None
    ) -> None:
        """
        Send the summary to a wastebin endpoint via HTTP POST with the expected JSON payload.
        """
        payload = {"text": summary}
        if extension is not None:
            payload["extension"] = extension
        if title is not None:
            payload["title"] = title
        if expires is not None:
            payload["expires"] = expires
        if burn_after_reading is not None:
            payload["burn_after_reading"] = burn_after_reading
        if password is not None:
            payload["password"] = password
        print(f"Sending summary to wastebin endpoint: {self.wastebin_url}")
        try:
            response = requests.post(self.wastebin_url, json=payload, timeout=120)
            response.raise_for_status()
            print(f"Summary posted successfully. Wastebin response: {response.text}")
            result = response.json()
            path = result.get("path")
            if path:
                # Remove trailing slash from base URL if present
                base_url = self.wastebin_url.rstrip("/")
                # Remove /api/paste or similar API path to get the base site URL
                if "/api/" in base_url:
                    base_url = base_url.split("/api/")[0]
                self.summary_url = f"{base_url}{path}"
                print(f"Summary URL: {self.summary_url}")
            else:
                self.summary_url = None
        except requests.exceptions.HTTPError as e:
          if response.status_code == 413:
              print("Error: The summary is too large to upload (HTTP 413 Payload Too Large).")
          else:
              print(f"HTTP error occurred: {e}")
        
        except Exception as e:
            print(f"Failed to post summary to wastebin: {e}")

    def ping_ntfy(self) -> None:
        """
        Ping ntfy to with the link to the summary in wastebin.
        """
        print("Pinging ntfy...")
        data = f"New PMP summary available here: {self.summary_url}"
        headers = {"Tags": "heavy_check_mark,pmp-summary,cron-job"}

        try:
            response = requests.post(default_ntfy_url, data=data, headers=headers)
            response.raise_for_status()
            print(f"Ntfy response: {response.text}")
        except Exception as e:
            print(f"Failed to ping ntfy: {e}")

    def run(self) -> None:
        """
        Run the summarization workflow.
        """
        start_time = time.time()
        video_id = self.get_video_id()

        # Retry logic for captions
        max_retries = 2
        retry_delay = 1800  # 30 minutes in seconds
        attempt = 0
        text = None
        while attempt <= max_retries:
            try:
                text = self.get_captions(video_id)
                break
            except Exception as e:
                attempt += 1
                if attempt > max_retries:
                    print(f"Failed to get captions after {max_retries + 1} attempts: {e}")
                    return
                print(f"Captions not available yet (attempt {attempt}/{max_retries + 1}): {e}")
                print(f"Sleeping for {retry_delay // 60} minutes before retrying...")
                time.sleep(retry_delay)

        chunks = self.chunk_text(text)
        summaries = self.summarize_chunks(chunks)
        final_summary = "\n".join(summaries)
        self.send_to_wastebin(
            summary=final_summary,
            extension="txt",
            title="PreMarket Prep Summary - " + datetime.datetime.now().strftime("%Y-%m-%d"),
            expires=86400  # 1 day
        )
        self.ping_ntfy()
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"Execution time: {execution_time:.6f} seconds")


if __name__ == "__main__":
    summarizer = PreMarketPrepSummarizer()
    summarizer.run()