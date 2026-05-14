import cv2
import numpy as np
import os
import glob


def detect_timing_marks(gray):
    """
    Detect the solid dark timing marks along the 4 edges of the OMR sheet.
    These are distinct from bubble circles - they are solid, dark rectangles.
    """
    h, w = gray.shape

    # Hard threshold - timing marks are very dark (< 80 intensity)
    _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    marks = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        x, y, cw, ch = cv2.boundingRect(cnt)

        # Timing marks are solid medium-sized rectangles
        if area < 200 or area > 10000:
            continue

        # Check solidity (timing marks are filled rectangles)
        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0:
            continue
        solidity = area / hull_area
        if solidity < 0.7:
            continue

        aspect = max(cw, ch) / (min(cw, ch) + 1e-5)
        if aspect > 5:
            continue

        cx, cy = x + cw / 2, y + ch / 2
        marks.append((cx, cy, cw, ch, area))

    return np.array(marks) if marks else None


def classify_edge_marks(marks):
    """
    Classify timing marks into left, right, top, bottom edges.

    Timing marks form:
    - Left column: dense cluster at the leftmost x positions
    - Right column: dense cluster at the rightmost x positions
    - Top row: marks at the first (topmost) y-level of timing marks
    - Bottom row: marks at the last (bottommost) y-level of timing marks
    """
    all_cx = marks[:, 0]
    all_cy = marks[:, 1]

    # --- Identify left and right columns ---
    # Histogram of x positions to find the two edge columns
    x_sorted = np.sort(np.unique(np.round(all_cx, -1)))  # round to nearest 10

    # Left column: marks near the minimum x
    # Right column: marks near the maximum x
    x_min = np.min(all_cx)
    x_max = np.max(all_cx)
    x_range = x_max - x_min

    # Marks within 5% of the left/right edge
    left_threshold = x_min + x_range * 0.05
    right_threshold = x_max - x_range * 0.05

    left_marks = marks[all_cx <= left_threshold]
    right_marks = marks[all_cx >= right_threshold]

    # --- Identify top and bottom rows ---
    # The top row contains the first timing marks (smallest y)
    # The bottom row contains the last timing marks (largest y)
    y_min = np.min(all_cy)
    y_max = np.max(all_cy)
    y_range = y_max - y_min

    # The timing marks repeat at regular intervals vertically.
    # Top row: marks at the very first y-level (within 3% of top)
    # Bottom row: marks at the very last y-level (within 3% of bottom)
    top_threshold = y_min + y_range * 0.03
    bottom_threshold = y_max - y_range * 0.03

    top_marks = marks[all_cy <= top_threshold]
    bottom_marks = marks[all_cy >= bottom_threshold]

    return left_marks, right_marks, top_marks, bottom_marks


def fit_line_ransac(x_coords, y_coords, iterations=3, percentile=70, min_pts=3):
    """Fit a line with iterative outlier removal."""
    if len(x_coords) < min_pts:
        return None
    coeffs = np.polyfit(x_coords, y_coords, 1)
    for _ in range(iterations):
        residuals = np.abs(y_coords - np.polyval(coeffs, x_coords))
        thresh = np.percentile(residuals, percentile)
        inliers = residuals <= thresh
        if np.sum(inliers) < 3:
            break
        coeffs = np.polyfit(x_coords[inliers], y_coords[inliers], 1)
    return coeffs


def find_boundary_lines(marks):
    """
    Fit 4 lines through the timing marks on each edge.
    Returns dict with keys: left, right, top, bottom
    - left/right: x = a*y + b (vertical lines parameterized by y)
    - top/bottom: y = a*x + b (horizontal lines parameterized by x)
    """
    left_marks, right_marks, top_marks, bottom_marks = classify_edge_marks(marks)

    lines = {}

    # Left edge: x = f(y)
    if len(left_marks) >= 3:
        coeffs = fit_line_ransac(left_marks[:, 1], left_marks[:, 0])
        if coeffs is not None:
            lines['left'] = coeffs

    # Right edge: x = f(y)
    if len(right_marks) >= 3:
        coeffs = fit_line_ransac(right_marks[:, 1], right_marks[:, 0])
        if coeffs is not None:
            lines['right'] = coeffs

    # Top edge: y = f(x) - allow fewer marks (2) since edges can be cut
    if len(top_marks) >= 2:
        coeffs = fit_line_ransac(top_marks[:, 0], top_marks[:, 1], min_pts=2)
        if coeffs is not None:
            lines['top'] = coeffs

    # Bottom edge: y = f(x) - allow fewer marks (2) since edges can be cut
    if len(bottom_marks) >= 2:
        coeffs = fit_line_ransac(bottom_marks[:, 0], bottom_marks[:, 1], min_pts=2)
        if coeffs is not None:
            lines['bottom'] = coeffs

    # Fallback: if we have 3 of 4 lines, infer the missing one.
    # The OMR sheet has a known aspect ratio (~1:2.33 width:height).
    # Use the left/right lines to estimate sheet width, then derive missing edge.
    if len(lines) == 3:
        if 'top' not in lines and 'bottom' in lines and 'left' in lines and 'right' in lines:
            # Infer top from bottom: top is parallel to bottom, offset by sheet height
            # Estimate height from left line span
            a_b, b_b = lines['bottom']
            # Get y positions of left marks to estimate sheet height
            y_span = left_marks[:, 1].max() - left_marks[:, 1].min()
            top_y = lines['bottom'][1] - y_span  # approximate
            lines['top'] = (a_b, top_y)
        elif 'bottom' not in lines and 'top' in lines and 'left' in lines and 'right' in lines:
            # Infer bottom from top: bottom is parallel to top, offset by sheet height
            a_t, b_t = lines['top']
            y_span = left_marks[:, 1].max() - left_marks[:, 1].min()
            bottom_y = lines['top'][1] + y_span
            lines['bottom'] = (a_t, bottom_y)

    return lines


def intersect_lines(lines):
    """
    Find the 4 corners by intersecting the edge lines.
    """
    corners = {}

    def intersect_lr_tb(lr_coeffs, tb_coeffs):
        # lr: x = a*y + b
        # tb: y = c*x + d
        a, b = lr_coeffs
        c, d = tb_coeffs
        denom = 1 - a * c
        if abs(denom) < 1e-10:
            return None
        x = (a * d + b) / denom
        y = c * x + d
        return (x, y)

    for corner_name, lr_key, tb_key in [
        ('top_left', 'left', 'top'),
        ('top_right', 'right', 'top'),
        ('bottom_left', 'left', 'bottom'),
        ('bottom_right', 'right', 'bottom'),
    ]:
        if lr_key in lines and tb_key in lines:
            pt = intersect_lr_tb(lines[lr_key], lines[tb_key])
            if pt:
                corners[corner_name] = pt

    return corners


def crop_omr_sheet(image_path, output_path, target_width=600, target_height=1400, debug_dir=None):
    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: Could not read {image_path}")
        return False

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_blur = cv2.GaussianBlur(gray, (3, 3), 0)

    marks = detect_timing_marks(gray_blur)
    if marks is None or len(marks) < 10:
        print(f"WARNING: Not enough timing marks found in {image_path}")
        return False

    lines = find_boundary_lines(marks)

    if len(lines) < 4:
        print(f"WARNING: Could not detect all 4 edge lines for {image_path}")
        print(f"  Detected edges: {list(lines.keys())}")
        return False

    corners = intersect_lines(lines)

    if len(corners) < 4:
        print(f"WARNING: Could not find all 4 corners for {image_path}")
        return False

    # Source points (detected corners) - order: TL, TR, BR, BL
    src_pts = np.array([
        corners['top_left'],
        corners['top_right'],
        corners['bottom_right'],
        corners['bottom_left']
    ], dtype=np.float32)

    # Destination points
    dst_pts = np.array([
        [0, 0],
        [target_width - 1, 0],
        [target_width - 1, target_height - 1],
        [0, target_height - 1]
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    cropped = cv2.warpPerspective(img, M, (target_width, target_height))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, cropped)
    print(f"OK: {os.path.basename(image_path)} -> {output_path}")

    # Debug image
    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        debug_img = img.copy()

        # Draw all timing marks
        for m in marks:
            cx, cy = int(m[0]), int(m[1])
            cv2.circle(debug_img, (cx, cy), 5, (0, 255, 0), -1)

        # Draw classified marks
        left_m, right_m, top_m, bottom_m = classify_edge_marks(marks)
        for m in left_m:
            cv2.circle(debug_img, (int(m[0]), int(m[1])), 7, (255, 0, 0), 2)
        for m in right_m:
            cv2.circle(debug_img, (int(m[0]), int(m[1])), 7, (0, 0, 255), 2)
        for m in top_m:
            cv2.circle(debug_img, (int(m[0]), int(m[1])), 7, (0, 255, 255), 2)
        for m in bottom_m:
            cv2.circle(debug_img, (int(m[0]), int(m[1])), 7, (255, 0, 255), 2)

        # Draw fitted lines
        colors = {'left': (255, 0, 0), 'right': (0, 0, 255),
                  'top': (0, 255, 255), 'bottom': (255, 0, 255)}
        h_img, w_img = gray.shape
        for name, coeffs in lines.items():
            color = colors[name]
            if name in ('left', 'right'):
                y1, y2 = 0, h_img - 1
                x1 = int(coeffs[0] * y1 + coeffs[1])
                x2 = int(coeffs[0] * y2 + coeffs[1])
                cv2.line(debug_img, (x1, y1), (x2, y2), color, 2)
            else:
                x1, x2 = 0, w_img - 1
                y1 = int(coeffs[0] * x1 + coeffs[1])
                y2 = int(coeffs[0] * x2 + coeffs[1])
                cv2.line(debug_img, (x1, y1), (x2, y2), color, 2)

        # Draw corners
        for name, (cx, cy) in corners.items():
            cv2.circle(debug_img, (int(cx), int(cy)), 10, (0, 0, 255), 3)

        cv2.imwrite(os.path.join(debug_dir, os.path.basename(image_path)), debug_img)

    return True


def process_folder(input_dir, output_dir, debug_dir):
    images = sorted(glob.glob(os.path.join(input_dir, "*.jpg")))
    print(f"\nFound {len(images)} images in {input_dir}")

    success = 0
    for img_path in images:
        fname = os.path.basename(img_path)
        out_path = os.path.join(output_dir, fname)
        if crop_omr_sheet(img_path, out_path, debug_dir=debug_dir):
            success += 1

    print(f"Done: {success}/{len(images)} images cropped successfully")


def main():
    parts = [
        ("data screen/part-d/01", "output/cropped/part-d", "output/debug/part-d"),
        ("data screen/part-c/01", "output/cropped/part-c", "output/debug/part-c"),
    ]
    for input_dir, output_dir, debug_dir in parts:
        process_folder(input_dir, output_dir, debug_dir)


if __name__ == "__main__":
    main()
