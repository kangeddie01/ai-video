from dataclasses import dataclass, field
from typing import List, Optional

from src.model.text_style import TextStyle

@dataclass
class VideoModel:

    bg_type:str #images|video    
    bg_images: list[str]
    text_list: list[TextStyle] = field(default_factory=list)
    textbox_image: Optional[str] = None
    textbox_width: int = 1500
    title_txt: Optional[str] = None    
    text_style: TextStyle | None = None
    title_text_style: TextStyle | None = None
    pause: float = 0.4
    fadeout_duration: int = 0
