"""Frame sampling interface.

The prototype's contract with video: a video path plus a sampling rate
goes in, a list of frame references comes out. In the scaffold, frame
references are identifiers. The real sampler (ffmpeg extraction, scene
segmentation for the hosted segmentation pass) slots in behind
sample_frames without the rest of the pipeline noticing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class FrameSet:
    source: str
    frames: list[str]
    fps_sampled: float


def sample_frames(video_path: str | Path, fps: float = 1.0) -> FrameSet:
    """Return frame references for a video.

    Scaffold behaviour: if the path is a directory of images, the
    images are the frames. If it is a video file, frame identifiers are
    generated at the requested rate for a nominal pass; real extraction
    lands here during the mechanism prototype.
    """
    path = Path(video_path)
    if path.is_dir():
        images = sorted(
            str(p) for p in path.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        )
        return FrameSet(source=str(path), frames=images, fps_sampled=fps)
    if path.is_file():
        count = 12
        frames = [f"frame_{i:06d}" for i in range(0, count * 30, 30)]
        return FrameSet(source=str(path), frames=frames, fps_sampled=fps)
    raise FileNotFoundError(f"video path not found: {video_path}")
