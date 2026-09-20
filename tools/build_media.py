"""Create compact README GIF + MP4 from a recorded simulation GIF.

Preserves simulation-time duration. Does not add generated/interpolated motion.
Usage: python tools/build_media.py runs/demo/trajectory.gif docs/media/demo
"""

import argparse
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageSequence


def build(source, prefix):
    prefix.parent.mkdir(parents=True, exist_ok=True)
    frames, durations = [], []
    with Image.open(source) as image:
        for frame in ImageSequence.Iterator(image):
            frames.append(frame.convert("RGB").copy())
            durations.append(frame.info.get("duration", 50))
    # Sample existing frames at 10 fps; retain the final partial interval.
    total = sum(durations)
    samples = []
    output_durations = []
    index = 0
    boundary = durations[0]
    for time in range(0, total, 100):
        while time >= boundary and index < len(frames) - 1:
            index += 1
            boundary += durations[index]
        samples.append(frames[index].resize((320, 320), Image.Resampling.LANCZOS))
        output_durations.append(min(100, total - time))
    palette_sheet = Image.new("RGB", (320, 240))
    for i in range(12):
        frame = samples[min(i * len(samples) // 12, len(samples) - 1)].resize((80, 80))
        palette_sheet.paste(frame, (i % 4 * 80, i // 4 * 80))
    palette = palette_sheet.quantize(colors=128)
    quantized = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in samples]
    quantized[0].save(
        prefix.with_suffix(".gif"),
        save_all=True,
        append_images=quantized[1:],
        duration=output_durations,
        loop=0,
        optimize=True,
    )
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-c:v",
            "libx264",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(prefix.with_suffix(".mp4")),
        ],
        check=True,
    )
    with Image.open(prefix.with_suffix(".gif")) as image:
        assert sum(f.info["duration"] for f in ImageSequence.Iterator(image)) == total
    print(f"{prefix}: {total / 1000:.2f}s simulation time, {len(samples)} GIF samples")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("prefix", type=Path)
    args = p.parse_args()
    build(args.source, args.prefix)
