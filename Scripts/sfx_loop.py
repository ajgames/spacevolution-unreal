"""Make a seamless loop from a stretch of an audio file by crossfading its tail into its head.

Needs numpy and soundfile, so Scripts/sfx.py runs it with the claude-music Stable Audio environment's Python:
  python sfx_loop.py <in> <out.wav> [--start S] [--end E] [--crossfade C]
"""
import argparse
import sys

import numpy as np
import soundfile as sf


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source")
    p.add_argument("out")
    p.add_argument("--start", type=float, default=0.0, help="Seconds to skip, e.g. a fade-in")
    p.add_argument("--end", type=float, default=None, help="Where the loop ends, before any fade-out")
    p.add_argument("--crossfade", type=float, default=1.5, help="Seconds of tail blended into the head")
    args = p.parse_args()

    audio, rate = sf.read(args.source, always_2d=True)
    start = int(args.start * rate)
    end = len(audio) if args.end is None else min(len(audio), int(args.end * rate))
    segment = audio[start:end]
    blend = int(args.crossfade * rate)
    if blend < 1 or len(segment) < 3 * blend:
        sys.exit(f"Need at least 3x the crossfade ({3 * args.crossfade:.1f}s) between --start and --end")

    # Equal-power fades: the tail fades out as the head fades in, so the wrap from the end of the loop back to
    # its start continues straight on from the tail's next sample.
    t = np.linspace(0.0, 1.0, blend)[:, None] * (np.pi / 2)
    head = segment[:blend] * np.sin(t) + segment[-blend:] * np.cos(t)
    loop = np.concatenate([head, segment[blend:-blend]])
    loop *= min(1.0, 0.891 / max(float(np.abs(loop).max()), 1e-9))  # -1 dBFS ceiling
    sf.write(args.out, loop, rate, subtype="PCM_24")
    print(f"{len(loop) / rate:.2f}")


if __name__ == "__main__":
    main()
