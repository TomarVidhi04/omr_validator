"""
Extracts ONLY the three handwritten Part-D sections per sheet:
  - registration_no
  - roll_no_written
  - course_code_written

Run: python extract_handwritten_partd.py

Reads cropped Part-D sheets from:   output/cropped/part-d/
Writes section crops to:            output/sections/part-d/<sheet>/

Output path matches what manage.py ingest_data reads, so after running this
you can go straight to:
    python manage.py ingest_data
    python manage.py run_ocr
"""
import cv2
import os
import glob

# Same canonical sheet size used by extract_sections.py
TARGET_SIZE = (600, 1500)  # (width, height)

# Only the three handwritten sections we care about.
# Coordinates are in the TARGET_SIZE coordinate space.
SECTIONS_HANDWRITTEN = {
    "registration_no":      (20, 292, 592, 385),
    "roll_no_written":      (20, 385, 408, 465),
    "course_code_written":  (122, 855, 428, 965),
}


def extract_handwritten(image_path, output_dir, normalize=True):
    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: Could not read {image_path}")
        return False

    h, w = img.shape[:2]
    print(f"  Input size: {w}x{h}", end="")

    if normalize and (w, h) != TARGET_SIZE:
        img = cv2.resize(img, TARGET_SIZE, interpolation=cv2.INTER_AREA)
        cv2.imwrite(image_path, img)
        print(f"  ->  resized to {TARGET_SIZE[0]}x{TARGET_SIZE[1]}", end="")
    print()

    fname = os.path.splitext(os.path.basename(image_path))[0]
    sheet_dir = os.path.join(output_dir, fname)
    os.makedirs(sheet_dir, exist_ok=True)

    for section_name, (x1, y1, x2, y2) in SECTIONS_HANDWRITTEN.items():
        x1c, y1c = max(0, x1), max(0, y1)
        x2c, y2c = min(img.shape[1], x2), min(img.shape[0], y2)
        crop = img[y1c:y2c, x1c:x2c]
        if crop.size == 0:
            print(f"  WARNING: empty crop for {section_name}")
            continue
        out_path = os.path.join(sheet_dir, f"{section_name}.jpg")
        cv2.imwrite(out_path, crop)

    print(f"OK: {fname} -> {len(SECTIONS_HANDWRITTEN)} handwritten sections extracted")
    return True


def main():
    input_dir  = "output/cropped/part-d"
    output_dir = "output/sections/part-d"

    images = sorted(glob.glob(os.path.join(input_dir, "*.jpg")))
    print(f"Found {len(images)} cropped Part-D images")

    if not images:
        print(f"No images in {input_dir}.")
        print(f"Run the crop step first (e.g. crop_omr.py)")
        return

    ok = fail = 0
    for img_path in images:
        if extract_handwritten(img_path, output_dir):
            ok += 1
        else:
            fail += 1

    print(f"\nDone. {ok} ok, {fail} failed.")
    print(f"Sections saved to {output_dir}")


if __name__ == "__main__":
    main()
