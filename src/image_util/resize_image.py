import cv2

def resize_image(input_path, output_path, target_size :tuple)->None:
    img = cv2.imread(input_path)

    h, w = img.shape[:2]
    target_width, target_height = target_size
    target_ratio = target_width / target_height
    new_h = int(w / target_ratio)

    top = (h - new_h) // 2
    cropped = img[top:top + new_h, :]

    result = cv2.resize(cropped, (target_width, target_height))

    cv2.imwrite(output_path, result)
    