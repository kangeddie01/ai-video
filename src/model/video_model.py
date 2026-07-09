from dataclasses import dataclass, field
from typing import Optional

from src.model.text_style import TextStyle

@dataclass
class VideoModel:
    
    bg_type:str #images|video    
    bg_images: list[str]
    textbox_image: Optional[str] = None
    textbox_width: int = 1500
    title_txt: Optional[str] = None

    # title_position: Optional[tuple[int, int]] = (50, 50)
    # title_color: tuple[int, int, int, int] = (0, 0, 0, 255)
    # title_font_path: str = "c:\\WINDOWS\\Fonts\\H2GTRE.TTF"
    # title_font_size: int = 60
    # title_text_effect: list[str] = field(default_factory=list)

    title_text_style: TextStyle = field(default_factory=TextStyle)

    # font_path: str = "c:\\WINDOWS\\Fonts\\H2MJRE.TTF"
    # font_size: int = 58
    # text_color: tuple[int, int, int, int] = (45, 35, 25, 255)
    # text_effect: list[str] = field(default_factory=list)
    
    text_style: TextStyle = field(default_factory=TextStyle)
    pause: float = 0.4
    fadeout_duration: int = 0