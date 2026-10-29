#!/usr/bin/env python3
"""Fetch a short video's metadata + spoken-word transcript for content analysis.

Usage:
    python3 scripts/analyze_video.py <url> [options]

Given a video URL (Instagram Reel/Post, TikTok, YouTube Shorts, etc.), this
downloads the audio track, runs it through a local Whisper model to produce a
transcript, and prints a single JSON object containing the post's metadata
(caption, like/view/comment counts, upload date) and the transcript (full
text plus timestamped segments). It does not interpret or summarize the
content -- that happens afterwards, by feeding this JSON to an LLM.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path


def fetch_and_download(
    url: str, workdir: Path, cookies: str | None, cookies_from_browser: str | None
) -> tuple[dict, Path]:
    """Single yt-dlp pass: extracts metadata and downloads+extracts audio.

    Doing this as one request (instead of a metadata-only call followed by a
    separate download call) avoids tripping platforms' rate limits, which
    trigger on two requests for the same URL in quick succession.
    """
    import yt_dlp

    out_template = str(workdir / "audio.%(ext)s")
    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
    }
    if cookies:
        opts["cookiefile"] = cookies
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    metadata = {
        "url": url,
        "extractor": info.get("extractor"),
        "title": info.get("title"),
        "caption": info.get("description"),
        "uploader": info.get("uploader") or info.get("channel"),
        "upload_date": info.get("upload_date"),
        "duration_seconds": info.get("duration"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "comment_count": info.get("comment_count"),
        "repost_count": info.get("repost_count"),
        "hashtags": info.get("tags") or info.get("categories"),
    }

    audio_files = list(workdir.glob("audio.*"))
    if not audio_files:
        raise RuntimeError("yt-dlp finished but no audio file was produced")
    return metadata, audio_files[0]


def transcribe(audio_path: Path, model_size: str, language: str | None) -> dict:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments_iter, info = model.transcribe(str(audio_path), language=language, vad_filter=True)

    segments = []
    full_text_parts = []
    for seg in segments_iter:
        text = seg.text.strip()
        segments.append({"start": round(seg.start, 2), "end": round(seg.end, 2), "text": text})
        full_text_parts.append(text)

    return {
        "detected_language": info.language,
        "language_probability": round(info.language_probability, 3),
        "full_text": " ".join(full_text_parts),
        "segments": segments,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="Video URL (Instagram, TikTok, YouTube, etc.)")
    parser.add_argument("--model", default="medium", help="faster-whisper model size: tiny/base/small/medium/large-v3 (default: medium)")
    parser.add_argument("--language", default=None, help="Force transcription language, e.g. zh, en (default: auto-detect)")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON result to this file instead of only stdout")
    parser.add_argument("--keep-media", action="store_true", help="Keep the downloaded audio file instead of deleting it")
    parser.add_argument("--cookies", default=None, help="Path to a cookies.txt file (needed for private/login-gated posts)")
    parser.add_argument("--cookies-from-browser", default=None, help="Browser name to read cookies from, e.g. chrome, firefox")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="video_analyze_") as tmp:
        workdir = Path(tmp)

        print("Fetching metadata and downloading audio...", file=sys.stderr)
        try:
            metadata, audio_path = fetch_and_download(args.url, workdir, args.cookies, args.cookies_from_browser)
        except Exception as e:
            print(json.dumps({"error": f"failed to fetch/download: {e}"}, ensure_ascii=False))
            sys.exit(1)

        if args.keep_media:
            kept_path = Path.cwd() / audio_path.name
            kept_path.write_bytes(audio_path.read_bytes())
            print(f"Kept audio at {kept_path}", file=sys.stderr)

        print(f"Transcribing with Whisper model '{args.model}' (this can take a while on CPU)...", file=sys.stderr)
        try:
            transcript = transcribe(audio_path, args.model, args.language)
        except Exception as e:
            print(json.dumps({"error": f"failed to transcribe: {e}", "metadata": metadata}, ensure_ascii=False))
            sys.exit(1)

    result = {"metadata": metadata, "transcript": transcript}
    output_json = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        args.output.write_text(output_json, encoding="utf-8")
        print(f"Wrote result to {args.output}", file=sys.stderr)

    print(output_json)


if __name__ == "__main__":
    main()
