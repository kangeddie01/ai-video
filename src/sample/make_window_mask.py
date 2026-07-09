# 이 스크립트는 입력 이미지에서 창문을 탐지하고,
# 탐지된 창문 영역에 대한 마스크를 생성하여 저장합니다.
# Grounding DINO로 텍스트 기반 창문 박스를 찾고,
# SAM2로 해당 박스를 기반으로 마스크를 만들어 후처리합니다.
# 결과 마스크와 마스크 영역이 표시된 미리보기 이미지를 출력합니다.

import os
import cv2
import torch
import numpy as np
from PIL import Image
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor




# =========================
# 설정
# =========================

IMAGE_PATH = "resources/images/living_room1.png"
OUTPUT_MASK = "resources/masks/window_mask.png"
OUTPUT_PREVIEW = "window_mask_preview.jpg"

TEXT_PROMPT = "window."
BOX_THRESHOLD = 0.25
TEXT_THRESHOLD = 0.25

SAM2_DIR = "sam2"
SAM2_CONFIG = "configs/sam2.1/sam2.1_hiera_l.yaml"
SAM2_CHECKPOINT = "checkpoints/sam2.1_hiera_large.pt"

device = "cuda" if torch.cuda.is_available() else "cpu"

print("Device:", device)


# =========================
# 경로 확인
# =========================

sam2_checkpoint_path = os.path.join(SAM2_DIR, SAM2_CHECKPOINT)
print("체크포인트 경로 : "+sam2_checkpoint_path)
if not os.path.exists(IMAGE_PATH):
    raise FileNotFoundError(f"이미지를 찾을 수 없습니다: {IMAGE_PATH}")

if not os.path.exists(sam2_checkpoint_path):
    raise FileNotFoundError(f"SAM2 체크포인트를 찾을 수 없습니다: {sam2_checkpoint_path}")


# =========================
# 이미지 로드
# =========================

image_pil = Image.open(IMAGE_PATH).convert("RGB")
image_np = np.array(image_pil)
height, width = image_np.shape[:2]


# =========================
# 1. Grounding DINO로 창문 찾기
# =========================

print("Grounding DINO 로딩 중...")

processor = AutoProcessor.from_pretrained("IDEA-Research/grounding-dino-base")
dino_model = AutoModelForZeroShotObjectDetection.from_pretrained(
    "IDEA-Research/grounding-dino-base"
).to(device)

inputs = processor(
    images=image_pil,
    text=TEXT_PROMPT,
    return_tensors="pt"
).to(device)

print("창문 탐지 중...")

with torch.no_grad():
    outputs = dino_model(**inputs)

results = processor.post_process_grounded_object_detection(
    outputs,
    inputs.input_ids,
    threshold=BOX_THRESHOLD,
    text_threshold=TEXT_THRESHOLD,
    target_sizes=[(height, width)]
)[0]

boxes = results["boxes"].detach().cpu().numpy()
scores = results["scores"].detach().cpu().numpy()

if len(boxes) == 0:
    raise RuntimeError(
        "창문을 찾지 못했습니다. TEXT_PROMPT를 'large window.' 또는 'glass window.'로 바꿔보세요."
    )

best_index = int(np.argmax(scores))
box = boxes[best_index]

print("탐지된 창문 박스:", box)
print("탐지 점수:", scores[best_index])


# =========================
# 2. SAM2로 마스크 생성
# =========================

print("SAM2 로딩 중...")

sam2_model = build_sam2(
    SAM2_CONFIG,
    sam2_checkpoint_path,
    device=device
)

predictor = SAM2ImagePredictor(sam2_model)
predictor.set_image(image_np)

print("마스크 생성 중...")

masks, sam_scores, _ = predictor.predict(
    box=box,
    multimask_output=True
)

best_mask_index = int(np.argmax(sam_scores))
mask = masks[best_mask_index].astype(np.uint8) * 255


# =========================
# 3. 마스크 후처리
# =========================

kernel = np.ones((9, 9), np.uint8)

mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
mask = cv2.GaussianBlur(mask, (11, 11), 0)

cv2.imwrite(OUTPUT_MASK, mask)


# =========================
# 4. 미리보기 이미지 저장
# =========================

preview = image_np.copy()
red_overlay = np.zeros_like(preview)
red_overlay[:, :, 0] = 255

mask_float = mask.astype(np.float32) / 255.0
mask_float = np.expand_dims(mask_float, axis=2)

preview = (
    preview * (1 - mask_float * 0.45)
    + red_overlay * (mask_float * 0.45)
).astype(np.uint8)

x1, y1, x2, y2 = box.astype(int)
preview = cv2.cvtColor(preview, cv2.COLOR_RGB2BGR)
cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 255, 0), 3)

cv2.imwrite(OUTPUT_PREVIEW, preview)

print("완료")
print("마스크 저장:", OUTPUT_MASK)
print("미리보기 저장:", OUTPUT_PREVIEW)