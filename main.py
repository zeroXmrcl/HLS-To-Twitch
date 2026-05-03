import os
import signal
import subprocess
import sys
import time
from dotenv import load_dotenv


def env(name: str, default: str | None = None, required: bool = False) -> str:
    """Read string env var"""
    value = os.getenv(name, default)

    if required and not value:
        print(f"Missing variable: {name}", file=sys.stderr)
        sys.exit(1)

    return value or ""


def env_bool(name: str, default: bool = False) -> bool:
    """Read boolean env var"""
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int | None = None, required: bool = False) -> int:
    """Read int env var"""
    value = os.getenv(name)

    if value is None or value == "":
        if required or default is None:
            print(f"Missing variable: {name}", file=sys.stderr)
            sys.exit(1)
        return default

    try:
        return int(value)
    except ValueError:
        print(f"Invalid integer for {name}: {value}", file=sys.stderr)
        sys.exit(1)


load_dotenv()

HLS_URL = env("HLS_URL", required=True)
TWITCH_STREAM_KEY = env("TWITCH_STREAM_KEY", required=True)
TWITCH_RTMP_URL = env("TWITCH_RTMP_URL", "rtmp://live.twitch.tv/app")

VIDEO_BITRATE = env("VIDEO_BITRATE", "3000k")
MAXRATE = env("MAXRATE", VIDEO_BITRATE)
BUFSIZE = env("BUFSIZE", "6000k")
FPS = env_int("FPS", 30)
GOP = env_int("GOP", FPS * 2)
PRESET = env("PRESET", "veryfast")

WIDTH = env("WIDTH", "")
HEIGHT = env("HEIGHT", "")

USE_SILENT_AUDIO = env_bool("USE_SILENT_AUDIO", True)
RESTART_DELAY_SECONDS = env_int("RESTART_DELAY_SECONDS", 10)


def ffmpeg_command() -> list[str]:
    """Build FFmpeg command"""
    output_url = f"{TWITCH_RTMP_URL}/{TWITCH_STREAM_KEY}"
    vf_filters = []
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-re",
        "-i",
        HLS_URL,
    ]

    if USE_SILENT_AUDIO:
        command += [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
        ]
    else:
        command += [
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
        ]

    if WIDTH and HEIGHT:
        vf_filters.append(
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease"
        )
        vf_filters.append(
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2"
        )

    if vf_filters:
        command += ["-vf", ",".join(vf_filters)]

    command += [
        "-c:v",
        "libx264",
        "-preset",
        PRESET,
        "-b:v",
        VIDEO_BITRATE,
        "-maxrate",
        MAXRATE,
        "-bufsize",
        BUFSIZE,
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(FPS),
        "-g",
        str(GOP),

        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "44100",
        "-ac",
        "2",

        "-f",
        "flv",
        output_url,
    ]

    return command


def run() -> None:
    """Run and restart FFmpeg"""
    stop_requested = False
    process: subprocess.Popen | None = None

    def handle_signal(signum, frame):
        """Stop FFmpeg on stop signal"""
        nonlocal stop_requested, process
        print(f"Stop signal ${stop_requested}. Stopping stream...")
        stop_requested = True

        if process and process.poll() is None:
            process.terminate()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    while not stop_requested:
        command = build_ffmpeg_command()

        print("Starting Stream...")
        print("Input:", env("HLS_URL"))
        print("Output", env("TWITCH_RTMP_URL"))
        print()

        try:
            process = subprocess.Popen(command)
            return_code = process.wait()
        except FileNotFoundError:
            print("FFmpeg not found. Install with: sudo apt install ffmpeg")
            sys.exit(1)

        if stop_requested:
            break

        print(f"FFmpeg exited with code {return_code}. Restart in {RESTART_DELAY_SECONDS} seconds...")
        time.sleep(RESTART_DELAY_SECONDS)

    print("Stream stopped.")


if __name__ == "__main__":
    run_forever()
