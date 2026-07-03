import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from ai_image_create import generate_image
from image_text_merge_new import merge_text_to_image
from load_bible_data import load_bible_json_data
from resize_image import resize_image




data = load_bible_json_data()


#print(data["verses"][0]["image_prompt"])
#generate_image(data["verses"][0]["image_prompt"], "resources/images/scene2.png")

size = (1920, 1080);

for verse in data["verses"]:
    print(f"Verse: {verse['script']}")
    print(f"Image Prompt: {verse['image_prompt']}")
    image_path = f"resources/images/bible/scene{data['verses'].index(verse) + 1}.png"
    output_path = f"resources/images/bible/scene{data['verses'].index(verse) + 1}_text.png"

    generate_image(verse["image_prompt"], image_path, size)

    resize_image(image_path, output_path, size)
    merge_text_to_image(
        image_path=output_path,
        output_path=output_path,
        text=verse["script"]
    )