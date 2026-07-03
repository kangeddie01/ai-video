from PIL import Image, ImageDraw

W, H = 1400, 360
OUTPUT = "resources/images/textbox.png"

# 투명 배경
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 반투명 검정 박스
draw.rounded_rectangle(
    (0, 0, W, H),
    radius=45,
    fill=(0, 0, 0, 170),
    outline=(255, 255, 255, 80),
    width=3
)

img.save(OUTPUT)
print("완료:", OUTPUT)