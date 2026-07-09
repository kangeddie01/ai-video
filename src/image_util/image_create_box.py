from PIL import Image, ImageDraw

def create_rounded_rectangle_image(width, height, radius, fill_color, outline_color, outline_width, output_path):
    # RGBA 모드의 투명 배경 이미지를 생성
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    # 그리기 객체 생성
    draw = ImageDraw.Draw(img)

    # 반투명 검정색 박스를 그리기
    # radius: 모서리 둥글기
    # fill: 내부 색상 (R, G, B, A)
    # outline: 테두리 색상
    # width: 테두리 굵기
    draw.rounded_rectangle(
        (0, 0, width, height),
        radius=radius,
        fill=fill_color,
        outline=(0, 0, 0, 100),
        # outline_width = outline_width,
        width=outline_width
    )

    # 결과 이미지 저장
    img.save(output_path)
    print("완료:", output_path)


    
# 출력 이미지 크기 정의 (너비 x 높이)
width, height = 1920, 700
# 저장할 파일 경로
output_path = f"resources/images/textbox_image_{width}_{height}1.png"

if __name__ == "__main__":
    create_rounded_rectangle_image(
        width=width,
        height=height,
        radius=20,
        fill_color=(245, 240, 225, 225),
        outline_color=(0, 0, 0, 100),
        outline_width=0,
        output_path=output_path
    )

