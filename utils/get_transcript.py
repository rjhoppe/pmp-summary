from youtube_transcript_api.formatters import TextFormatter
from youtube_transcript_api import YouTubeTranscriptApi

"""
This script is used to get the transcript of a video.
"""

def get_captions(video_id: str) -> str:
    """
    Get the transcript of a video.
    """
    captions = YouTubeTranscriptApi.get_transcript(video_id)
    formatter = TextFormatter()
    transcript = formatter.format_transcript(captions)
    return transcript


if __name__ == "__main__":
    video_id = "Fk9zXm9FNu8"
    ## Change this to the video id you want to get the transcript for
    transcript = get_captions(video_id)
    print(transcript)

    # save the transcript to a file
    with open("transcript.txt", "w") as f:
        f.write(transcript)