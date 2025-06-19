import datetime
import json
import os
import time
from typing import List, Optional

import requests
import tiktoken
from discord_webhook import DiscordWebhook
from dotenv import load_dotenv
from mistralai import Mistral
from youtube_search import YoutubeSearch
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv()

default_api_key = os.environ.get("MISTRAL_API_KEY")
default_model = "mistral-small-latest"
default_wastebin_url = os.environ.get("WASTEBIN_URL")
default_ntfy_url = os.environ.get("NTFY_URL")


class PreMarketPrepSummarizer:
    """
    Summarizes the most recent 'PreMarket Prep' YouTube stream using Mistral API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = default_model,
        wastebin_url: str = default_wastebin_url,
        summary_url: str = default_wastebin_url,
    ):
        self.api_key = api_key or default_api_key
        self.model = model
        self.client = Mistral(api_key=self.api_key)
        self.wastebin_url = wastebin_url
        self.summary_url = summary_url

    def get_video_id(
        self, channel_name: str = "PreMarket Prep", max_results: int = 5
    ) -> str:
        """
        Get the most recent video ID from the specified channel.
        """
        print("Getting the most recent stream's video id...")
        search_json = YoutubeSearch(channel_name, max_results=max_results).to_json()
        search = json.loads(search_json)
        for i in range(max_results):
            if search["videos"][i]["channel"] == channel_name:
                print("--------------------------------")
                print(f"Title: {search['videos'][i]['title']}")
                print(f"Publish Time: {search['videos'][i]['publish_time']}")
                print(f"ID: {search['videos'][i]['id']}")
                print("--------------------------------")
                return search["videos"][i]["id"]
        self.ping_error_ntfy(f"No video found for channel {channel_name}")
        raise ValueError(f"No video found for channel {channel_name}")

    def get_captions(self, video_id: str) -> str:
        """
        Extract captions from a YouTube video by ID.
        """
        print(f"Extracting captions for video ID: {video_id}")
        try:
            # Get transcript with explicit language preference
            captions = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=["en"],  # Prefer English captions
            )

            # Debug: Print the structure of the first caption
            if captions and len(captions) > 0:
                print(f"Retrieved {len(captions)} caption segments")
                print("First caption segment structure:")
                print(json.dumps(captions[0], indent=2))

            # Verify we have captions
            if not captions:
                raise ValueError("No captions were returned")

            # Custom formatting: just join the text with newlines
            # This avoids issues with the TextFormatter class
            formatted_text = []
            for caption in captions:
                if isinstance(caption, dict) and "text" in caption:
                    formatted_text.append(caption["text"])

            fmt_captions = "\n".join(formatted_text)

            if not fmt_captions.strip():
                raise ValueError("Formatted captions are empty")

            print(f"Successfully formatted {len(formatted_text)} caption segments")
            return fmt_captions

        except Exception as e:
            print(f"Error getting captions: {type(e).__name__}: {str(e)}")
            print("This could be because:")
            print("1. The video is too recent and captions aren't ready")
            print("2. The video doesn't have English captions")
            print("3. The caption format is unexpected")
            raise

    def chunk_text(
        self, text: str, max_tokens: int = 2048, overlap: int = 100
    ) -> List[str]:
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
                request = [
                    {"role": "user", "content": f"Summarize this text:\n\n{chunk}"}
                ]
                response = self.client.chat.complete(model=self.model, messages=request)
                summaries.append(response.choices[0].message.content)
            except Exception as e:
                print(f"Error summarizing chunk: {e}")
                summaries.append("")
        return summaries

    def consolidate_summaries(self, summaries: List[str]) -> str:
        """
        Consolidate multiple chunk summaries into a single, well-organized final summary.
        This removes redundancy while preserving unique information.
        """
        print("Consolidating summaries into final summary...")
        combined_summaries = "\n\n".join(
            [
                f"Section {i+1}:\n{summary}"
                for i, summary in enumerate(summaries)
                if summary.strip()
            ]
        )

        consolidation_prompt = f"""You are tasked with consolidating multiple summary sections from a financial trading show transcript into a single, well-organized final summary.

INSTRUCTIONS:
1. Combine all the information from the sections below into ONE comprehensive summary
2. Remove duplicate information and redundant points
3. Organize the content into logical sections with clear headings
4. Preserve ALL unique information - do not omit any specific details, stock tickers, prices, or insights
5. Use bullet points and clear formatting for readability
6. Group related topics together (e.g., all stock discussions, market news, earnings, etc.)
7. Maintain the chronological flow when relevant

INPUT SECTIONS TO CONSOLIDATE:
{combined_summaries}

OUTPUT: A single, well-organized summary with clear headings and no redundant information."""

        try:
            request = [{"role": "user", "content": consolidation_prompt}]
            response = self.client.chat.complete(model=self.model, messages=request)
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error consolidating summaries: {e}")
            # Fallback to simple concatenation if consolidation fails
            return "\n\n".join(summaries)

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
        password: str = None,
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
                print(
                    "Error: The summary is too large to upload (HTTP 413 Payload Too Large)."
                )
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
        headers = {"Tags": "rotating_light,pmp-summary,cron-job"}

        try:
            response = requests.post(default_ntfy_url, data=data, headers=headers)
            response.raise_for_status()
            print(f"Ntfy response: {response.text}")
        except Exception as e:
            print(f"Failed to ping ntfy: {e}")

    def ping_error_ntfy(self, error: str) -> None:
        """
        Ping ntfy to with a job failed error message.
        """
        print("Pinging ntfy...")
        data = f"PMP Summary job failed to run.Error: {error}"
        headers = {"Tags": "heavy_check_mark,pmp-summary,cron-job"}

        try:
            response = requests.post(default_ntfy_url, data=data, headers=headers)
            response.raise_for_status()
            print(f"Ntfy response: {response.text}")
        except Exception as e:
            print(f"Failed to ping ntfy: {e}")

    def ping_discord(self, summary: str) -> None:
        """
        Send the summary to a discord webhook in chunks of 2000 characters or less.
        Tries to split on natural boundaries like newlines and periods.
        """
        print("Sending summary to Discord in chunks...")
        webhook_url = os.getenv("WEBHOOK_URL")

        def split_on_boundary(text: str, limit: int) -> tuple[str, str]:
            """Split text at a natural boundary (newline, period, space) near the limit."""
            if len(text) <= limit:
                return text, ""

            # Try to split on double newline first
            pos = text.rfind("\n\n", 0, limit)
            if pos > limit * 0.75:  # Only use if we found a good split point
                return text[:pos], text[pos:].lstrip()

            # Try to split on single newline
            pos = text.rfind("\n", 0, limit)
            if pos > limit * 0.75:
                return text[:pos], text[pos:].lstrip()

            # Try to split on period + space
            pos = text.rfind(". ", 0, limit)
            if pos > limit * 0.75:
                return text[: pos + 1], text[pos + 1 :].lstrip()

            # Try to split on space
            pos = text.rfind(" ", 0, limit)
            if pos > limit * 0.75:
                return text[:pos], text[pos:].lstrip()

            # If all else fails, just split at the limit
            return text[:limit], text[limit:]

        try:
            remaining_text = summary
            chunk_num = 1

            while remaining_text:
                # Get next chunk
                chunk, remaining_text = split_on_boundary(
                    remaining_text, 1950
                )  # Leave room for chunk numbers

                # Add chunk numbering if there will be multiple chunks
                if len(summary) > 2000:
                    chunk = f"[Part {chunk_num}]\n{chunk}"

                # Send chunk
                webhook = DiscordWebhook(url=webhook_url, content=chunk)
                response = webhook.execute()
                print(f"Sent chunk {chunk_num}, status: {response.status_code}")

                chunk_num += 1

                # Small delay between messages to avoid rate limiting
                if remaining_text:
                    time.sleep(1)

            print(f"Successfully sent summary in {chunk_num - 1} chunks")

        except Exception as e:
            print(f"Error sending to Discord: {e}")

    def run(self) -> None:
        """
        Run the summarization workflow.
        """
        start_time = time.time()
        video_id = self.get_video_id()

        # # Retry logic for captions
        max_retries = 3  # Total number of attempts
        retry_delay = 1800  # 30 minutes in seconds
        text = None

        for attempt in range(max_retries):
            try:
                print(
                    f"Attempting to get captions (attempt {attempt + 1}/{max_retries})..."
                )
                text = self.get_captions(video_id)
                print("Successfully retrieved captions!")
                break
            except Exception as e:
                print(
                    f"Captions not available yet (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt + 1 < max_retries:  # Don't sleep on the last attempt
                    print(
                        f"Sleeping for {retry_delay // 60} minutes before retrying..."
                    )
                    time.sleep(retry_delay)
                else:
                    print(
                        f"Failed to get captions after {max_retries} attempts. Exiting."
                    )
                    self.ping_error_ntfy(
                        f"Failed to get captions after {max_retries} attempts. Exiting."
                    )
                    return

        chunks = self.chunk_text(text)
        summaries = self.summarize_chunks(chunks)
        final_summary = self.consolidate_summaries(summaries)
        self.ping_discord(final_summary)
        self.send_to_wastebin(
            summary=final_summary,
            extension="txt",
            title="PreMarket Prep Summary - "
            + datetime.datetime.now().strftime("%Y-%m-%d"),
            expires=86400,  # 1 day
        )
        self.ping_ntfy()
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"Execution time: {execution_time:.6f} seconds")


if __name__ == "__main__":
    summarizer = PreMarketPrepSummarizer()
    summarizer.run()
