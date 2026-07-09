from PIL import Image, ImageDraw, ImageFont

bg = Image.open("resources/images/scene2.png").convert("RGBA")
box = Image.open("resources/images/textbox.png").convert("RGBA")

text = "요한복음 1장 1절\n태초에 말씀이 계셨습니다."
font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 52)

# 박스 위치
x = (bg.width - box.width) // 2
y = bg.height - box.height - 80

bg.alpha_composite(box, (x, y))

draw = ImageDraw.Draw(bg)

# 텍스트 위치
draw.multiline_text(
    (x + 70, y + 80),
    text,
    font=font,
    fill=(255, 255, 255, 255),
    spacing=18
)

bg.convert("RGB").save("resources/images/final.png")
print("완료: resources/images/final.png")