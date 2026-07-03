import cv2
import numpy as np
import random

BACKGROUND_IMAGE = "resources/images/living_room1.png"
WINDOW_MASK = "resources/masks/window_mask.png"
OUTPUT_VIDEO = "resources/video/rain_window.mp4"

WIDTH = 1920
HEIGHT = 1080
FPS = 30
DURATION = 15
RAIN_COUNT = 900

background = cv2.imread(BACKGROUND_IMAGE)
background = cv2.resize(background, (WIDTH, HEIGHT))

mask = cv2.imread(WINDOW_MASK, cv2.IMREAD_GRAYSCALE)
mask = cv2.resize(mask, (WIDTH, HEIGHT))

# 마스크 부드럽게
mask = cv2.GaussianBlur(mask, (15, 15), 0)
mask_float = mask.astype(np.float32) / 255.0
mask_float = cv2.merge([mask_float, mask_float, mask_float])

raindrops = []
for _ in range(RAIN_COUNT):
    x = random.randint(0, WIDTH)
    y = random.randint(0, HEIGHT)
    speed = random.randint(14, 32)
    length = random.randint(20, 45)
    thickness = random.choice([1, 1, 1, 2])
    raindrops.append([x, y, speed, length, thickness])

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
writer = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, FPS, (WIDTH, HEIGHT))

total_frames = FPS * DURATION

for frame_index in range(total_frames):
    frame = background.copy()

    # 천천히 줌인
    zoom = 1 + frame_index * 0.00035
    new_w = int(WIDTH * zoom)
    new_h = int(HEIGHT * zoom)
    zoomed = cv2.resize(background, (new_w, new_h))
    x1 = (new_w - WIDTH) // 2
    y1 = (new_h - HEIGHT) // 2
    frame = zoomed[y1:y1 + HEIGHT, x1:x1 + WIDTH]

    rain_layer = np.zeros_like(frame)

    for drop in raindrops:
        x, y, speed, length, thickness = drop
        wind = 8

        cv2.line(
            rain_layer,
            (x, y),
            (x + wind, y + length),
            (215, 215, 235),
            thickness
        )

        drop[1] += speed
        drop[0] += 1

        if drop[1] > HEIGHT:
            drop[0] = random.randint(0, WIDTH)
            drop[1] = random.randint(-100, 0)

    rain_layer = cv2.GaussianBlur(rain_layer, (3, 3), 0)

    # 마스크 영역에만 비 적용
    rain_only_window = (rain_layer * mask_float).astype(np.uint8)

    frame = cv2.addWeighted(frame, 1.0, rain_only_window, 0.85, 0)

    # 창문 영역 살짝 흐림 = 젖은 유리 느낌
    blurred = cv2.GaussianBlur(frame, (7, 7), 0)
    frame = (
        frame * (1 - mask_float * 0.12)
        + blurred * (mask_float * 0.12)
    ).astype(np.uint8)

    writer.write(frame)

writer.release()

print("완성:", OUTPUT_VIDEO)