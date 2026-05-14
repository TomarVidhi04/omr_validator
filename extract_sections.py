import cv2
import os
import glob

# Target normalized size for Part-D cropped sheets.
# All coordinates below are calibrated for this exact size.
# Any input sheet is resized to this before section extraction.
TARGET_SIZE = (600, 1500)  # (width, height)

# Format: (x1, y1, x2, y2) in TARGET_SIZE coordinate space
SECTIONS = {
    "barcode_number":       (12, 30, 118, 268),
    "barcode":              (78, 22, 268, 290),
    "registration_no":      (10, 272, 592, 362),
    "roll_no_written":      (10, 358, 408, 448),
    "roll_no_bubbles":      (10, 420, 408, 810),
    "center_code_written":  (382, 358, 592, 448),
    "center_code_bubbles":  (382, 420, 592, 810),
    "year_sem_written":     (10, 822, 138, 898),
    "year_sem_bubbles":     (10, 882, 138, 1258),
    "course_code_written":  (122, 822, 428, 898),
    "course_code_bubbles":  (122, 882, 428, 1258),
    "session_written":      (412, 822, 592, 898),
    "session_bubbles":      (412, 882, 592, 1258),
    "exam_type":            (10, 1260, 398, 1390),
    "sitting":              (382, 1260, 592, 1390),
}


def extract_sections(image_path, output_dir, normalize=True):
    """Extract bubble sections.

    If normalize=True (default), resizes the input cropped sheet to TARGET_SIZE
    before slicing — this guarantees the section coordinates always land in
    the right place regardless of the scanner's output resolution.
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: Could not read {image_path}")
        return False

    h, w = img.shape[:2]
    print(f"  Input size: {w}x{h}", end="")

    if normalize and (w, h) != TARGET_SIZE:
        img = cv2.resize(img, TARGET_SIZE, interpolation=cv2.INTER_AREA)
        # Overwrite the cropped sheet on disk with the normalized version
        # so downstream UI / debugging shows the canonical size.
        cv2.imwrite(image_path, img)
        print(f"  ->  resized to {TARGET_SIZE[0]}x{TARGET_SIZE[1]}", end="")
    print()

    fname = os.path.splitext(os.path.basename(image_path))[0]
    sheet_dir = os.path.join(output_dir, fname)
    os.makedirs(sheet_dir, exist_ok=True)

    for section_name, (x1, y1, x2, y2) in SECTIONS.items():
        # Clamp to image bounds in case a coord is slightly out of range
        x1c, y1c = max(0, x1), max(0, y1)
        x2c, y2c = min(img.shape[1], x2), min(img.shape[0], y2)
        crop = img[y1c:y2c, x1c:x2c]
        if crop.size == 0:
            print(f"  WARNING: empty crop for {section_name} at ({x1},{y1})-({x2},{y2})")
            continue
        out_path = os.path.join(sheet_dir, f"{section_name}.jpg")
        cv2.imwrite(out_path, crop)

    print(f"OK: {fname} -> {len(SECTIONS)} sections extracted")
    return True


def draw_section_overlay(image_path, output_path):
    """Draw all section boxes on the image for verification."""
    img = cv2.imread(image_path)
    if img is None:
        return

    colors = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
        (255, 0, 255), (0, 255, 255), (128, 0, 255), (255, 128, 0),
        (0, 128, 255), (128, 255, 0), (255, 0, 128), (0, 255, 128),
        (200, 100, 50), (50, 100, 200), (100, 200, 50),
    ]

    for i, (name, (x1, y1, x2, y2)) in enumerate(SECTIONS.items()):
        color = colors[i % len(colors)]
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, name, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)

    cv2.imwrite(output_path, img)


def main():
    input_dir = "output/cropped/part-d"
    output_dir = "output/sections/part-d"
    debug_dir = "output/debug/sections"

    images = sorted(glob.glob(os.path.join(input_dir, "*.jpg")))
    print(f"Found {len(images)} cropped images")

    os.makedirs(debug_dir, exist_ok=True)

    for img_path in images:
        extract_sections(img_path, output_dir)
        # Save overlay for first image
        fname = os.path.basename(img_path)
        draw_section_overlay(img_path, os.path.join(debug_dir, fname))

    print(f"\nDone. Sections saved to {output_dir}")


if __name__ == "__main__":
    main()
