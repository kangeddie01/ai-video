from PIL import Image, ImageDraw, ImageFont
import textwrap


def merge_text_to_image(
    image_path: str = "images/scene2.png",
    output_path: str = "images/scene2_text.png",
    text: str | None = None,
    font_path: str = "c:\WINDOWS\Fonts\HMKMRHD.TTF",
    font_size: int = 60,
    max_text_width: int | None = None,
    spacing: int = 12,
    margin: int = 80,
) -> None:
    if text is None:
        text = (
            "요한복음 1장 1절\n\n"
            "태초에 말씀이 계셨습니다.\n"
            "그 말씀은 하나님과 함께 계셨고\n"
            "말씀은 하나님이셨습니다."
        )

    img = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)

    if max_text_width is None:
        max_text_width = img.width - margin * 2

    # Wrap the text so it fits within the allowed width.
    lines = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append("")
            continue

        wrapped = textwrap.wrap(paragraph, width=100)
        if not wrapped:
            lines.append("")
            continue

        # Adjust wrap width by pixel width
        line = ""
        for word in paragraph.split():
            test_line = f"{line} {word}".strip()
            line_width = draw.textlength(test_line, font=font)
            if line and line_width > max_text_width:
                lines.append(line)
                line = word
            else:
                line = test_line
        if line:
            lines.append(line)

    wrapped_text = "\n".join(lines)

    bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, spacing=spacing)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    x = (img.width - text_w) // 2
    y = (img.height - text_h) // 2

    draw.multiline_text(
        (x, y),
        wrapped_text,
        font=font,
        fill=(255, 255, 255, 255),
        spacing=spacing,
        align="center",
    )

    img.convert("RGB").save(output_path)
    print(f"Saved merged image to {output_path}")


if __name__ == "__main__":
    merge_text_to_image()
