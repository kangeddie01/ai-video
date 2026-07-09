import cv2
import math
import numpy as np

IMAGE = r"resources\images\bible\bg_sample2.png"

img = cv2.imread(IMAGE)

h, w = img.shape[:2]

fps = 30
duration = 10

writer = cv2.VideoWriter(
    "leaf_motion.mp4",
    cv2.VideoWriter_fourcc(*"mp4v"),
    fps,
    (w, h)
)

for frame in range(fps * duration):

    t = frame / fps

    map_x = np.zeros((h, w), np.float32)
    map_y = np.zeros((h, w), np.float32)

    for y in range(h):

        # 위쪽일수록 많이 흔들림
        strength = (1 - y / h) * 4  # 흔들림 크기 감소

        offset = math.sin(y * 0.04 + t * 2.5) * strength

        map_x[y, :] = np.arange(w) + offset
        map_y[y, :] = y

    warped = cv2.remap(
        img,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT
    )

    writer.write(warped)

writer.release()