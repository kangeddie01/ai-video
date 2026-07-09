from dataclasses import dataclass, field
from typing import Optional

from src.model.video_basic import VideoBasic
from src.model.video_model import VideoModel


@dataclass
class VideoAutoRequest:

    video_basic: VideoBasic = field(default_factory=VideoBasic)
    video_body: VideoModel = field(default_factory=VideoModel)
    video_intro: Optional[VideoModel] = None