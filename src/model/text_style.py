from dataclasses import dataclass, field
from typing import Optional

@dataclass
class TextStyle:    
    text_position: tuple[int | str, int | str] = ("center", "center")    
    alignment: tuple[str, str] = ("center", "center")
    font_path: str = "c:\\WINDOWS\\Fonts\\H2MJRE.TTF"
    font_size: int = 58
    text_color: tuple[int, int, int, int] = (45, 35, 25, 255)
    text_effect: list[str] = field(default_factory=list)
    text_max_width: int = 1920

