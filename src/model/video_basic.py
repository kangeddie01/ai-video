from dataclasses import dataclass, field

@dataclass
class VideoBasic:    
    output_path: str = "output/video.mp4"
    width:int =1920
    height:int =1080
    fps:int =30