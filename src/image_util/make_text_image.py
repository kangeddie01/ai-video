import uuid

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def make_text_image(text, video_basic, text_style, max_width = 1500):
    img = Image.new("RGBA", (video_basic.width, video_basic.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(text_style.font_path, text_style.font_size)

    align_x, align_y = text_style.alignment
    # effects = set(text_effect or [])
    font_size = text_style.font_size
    def wrap_text(draw_obj, font_obj):
        wrapped_lines = []
        
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                wrapped_lines.append("")
                continue

            words = line.split()
            current = ""
            for word in words:
                test_line = f"{current} {word}".strip()
                if draw_obj.textlength(test_line, font=font_obj) > max_width:
                    if current:
                        wrapped_lines.append(current)
                    current = word
                else:
                    current = test_line

            if current:
                wrapped_lines.append(current)

        return wrapped_lines

    line_gap = 24
    min_font_size = 24
    lines = wrap_text(draw, font)

    while font_size > min_font_size:
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_heights.append(bbox[3] - bbox[1])

        total_h = sum(line_heights) + line_gap * (len(lines) - 1)
        if total_h <= video_basic.height:
            break

        font_size -= 2
        font = ImageFont.truetype(text_style.font_path, font_size)
        lines = wrap_text(draw, font)

    total_h = sum(draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] for line in lines)
    total_h += line_gap * (len(lines) - 1)

    if align_y == "top":
        y = 0
    elif align_y == "bottom":
        y = video_basic.height - total_h
    else:
        y = (video_basic.height - total_h) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        if align_x == "left":
            x = 0
        elif align_x == "right":
            x = video_basic.width - text_w
        else:
            x = (video_basic.width - text_w) // 2


        if 'shadow' in text_style.text_effect:
            shadow_color = (
                255 - text_style.text_color[0],
                255 - text_style.text_color[1],
                255 - text_style.text_color[2]
            )            
            shadow_offset = max(1, int(font_size * 0.095))
            draw.text(
                (x + shadow_offset, y + shadow_offset),
                line,
                font=font,
                fill=shadow_color
            )

        draw.text((x, y), line, font=font, fill=text_style.text_color)

        if "underline" in text_style.text_effect:
            underline_y = bbox[3] + 3
            draw.line((bbox[0], underline_y, bbox[2], underline_y), fill=text_style.text_color, width=max(1, font_size // 30))

        y += (bbox[3] - bbox[1]) + line_gap

        # 밑줄
        if 'underline' in text_style.text_effect:
            underline_y = bbox[3] + 4
            draw.line((bbox[0], underline_y, bbox[2], underline_y), fill=text_style.text_color, width=2)

    # 이미지 임시 저장
    temp_dir = Path("output/temp_ffmpeg/text_images")
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_path = temp_dir / f"{uuid.uuid4().hex}.png"

    img.save(output_path)

    return {
        "image": np.array(img),
        "path": str(output_path)
    }