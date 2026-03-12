from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import pandas as pd
import re
import os
import numpy as np
import cv2

# >>> ADJUST THESE IF NEEDED <<<
PDF_PRE='Your/dir/for/logs'
PDF_PATH = "combined.pdf"
POPPLER_PATH = r"C:\poppler\Library\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

DPI = 300
N_ROWS = 25
OUT_CSV = "JB_signout_real_extracted.csv"

def flag(value, level):
    value = value.strip() if isinstance(value, str) else value
    return f"{level}:{value}"

def expand_range(text):
    text = text.replace(" ", "")
    if "-" in text:
        a, b = text.split("-", 1)
        if a.isdigit() and b.isdigit():
            return list(range(int(a), int(b) + 1))
    return text
def find_col_edges(vertical_img, min_gap=20):
    proj = np.sum(vertical_img, axis=0)
    xs = np.where(proj > 0)[0]
    cols = []
    current = [xs[0]]
    for x in xs[1:]:
        if x - current[-1] <= min_gap:
            current.append(x)
        else:
            cols.append(int(np.mean(current)))
            current = [x]
    cols.append(int(np.mean(current)))
    return cols

def find_row_edges(horizontal_img, min_gap=20):
    # Sum pixels along x-axis
    proj = np.sum(horizontal_img, axis=1)
    # Rows where ink exists
    ys = np.where(proj > 0)[0]
    # Group close y-values
    rows = []
    current = [ys[0]]
    for y in ys[1:]:
        if y - current[-1] <= min_gap:
            current.append(y)
        else:
            rows.append(int(np.mean(current)))
            current = [y]
    rows.append(int(np.mean(current)))
    return rows

def detect_table_lattice(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Binary image
    bw = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        15, 5
    )
    H, W = bw.shape
    # --- Detect horizontal lines (rows) ---
    h_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (W // 2, 1)
    )
    horizontal = cv2.morphologyEx(
        bw, cv2.MORPH_OPEN, h_kernel
    )
    #Image.fromarray(horizontal, 'L').save("horizontal.png") # 'L' mode is for grayscale images
    # --- Detect vertical lines (columns) ---
    v_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (1, H // 2)
    )
    vertical = cv2.morphologyEx(
        bw, cv2.MORPH_OPEN, v_kernel
    )
    row_edges = find_row_edges(horizontal)
    col_edges = find_col_edges(vertical)
    return row_edges, col_edges

def ocr_numeric_cell_1by1(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Boost contrast
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    # Binarize
    _, bw = cv2.threshold(
        gray, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        bw, connectivity=8
    )
    digits = []
    for i in range(1, num_labels):  # skip background
        x, y, w, h, area = stats[i]
        if area < 50:
            continue  # remove noise
        digit_crop = bw[y:y+h, x:x+w]
        # Resize per digit
        digit_crop = cv2.resize(
            digit_crop, (32, 32),
            interpolation=cv2.INTER_CUBIC
        )
        digits.append((x, digit_crop))
    digits = sorted(digits, key=lambda x: x[0])
    result = ""
    for i, d in digits:
        cv2.imwrite("filename"+str(i)+".png", d)
        txt = pytesseract.image_to_string(
            d,
            config="--psm 10 -c tessedit_char_whitelist=0123456789"
        ).strip()
        print(txt)
        if txt.isdigit():
            result += txt
    return result

def ocr_numeric_cell(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Boost contrast
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    # Binarize
    _, bw = cv2.threshold(
        gray, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    # Remove tiny noise (dots, dust)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
    # Thicken strokes
    bw = cv2.dilate(bw, kernel, iterations=1)
    # Upscale (CRITICAL for Tesseract)
    bw = cv2.resize(
        bw, None,
        fx=3, fy=3,
        interpolation=cv2.INTER_CUBIC
    )
    txt = pytesseract.image_to_string(
        bw,
        config="--oem 1 --psm 8 -c tessedit_char_whitelist=0123456789-"
    ).strip()
    return txt

def build_cells(rows, cols):
    cells = []
    for i in range(len(rows) - 1):
        for j in range(len(cols) - 1):
            cells.append((
                cols[j], rows[i],
                cols[j+1], rows[i+1]
            ))
    return cells
pages = convert_from_path(
    PDF_PRE +PDF_PATH,
    dpi=DPI,
    poppler_path=POPPLER_PATH
)
img_as_array = np.array(img)
records = []

for page_idx, img in enumerate(pages, start=1):
    img = img.rotate(-90, expand=True)
    img_as_array = np.array(img)
    row_edges, col_edges =detect_table_lattice(img_as_array)
    #W, H = img.size
    #row_h = H / N_ROWS
    COLS = {
        "id":   (col_edges[0], col_edges[1]),
        "date": (col_edges[1], col_edges[1]),
        "DF":   (col_edges[2], col_edges[3]),
        "B9":   (col_edges[3], col_edges[4]),
        "T":   (col_edges[4], col_edges[5]),
        "DMSO_F":   (col_edges[5], col_edges[6]),
    }
    ROWS = dict()
    for i in range(len(row_edges)-2):
        ROWS[i]=(row_edges[i+1], row_edges[i+2])
    for row in ROWS.keys():
        for col in COLS.keys():
            rec = {"page": page_idx, "row": row, "col": col}
            x1 = COLS[col][0]
            x2 = COLS[col][1]
            y1 = ROWS[row][0]
            y2 = ROWS[row][1]
            crop = img.crop((x1, y1, x2, y2))
            crop.save(str(row)+col+".png")
            txt = pytesseract.image_to_string(
                crop,
                config="--psm 7"
            ).strip()
            if cname == "id":
                m = re.search(r"\b\d{4,5}\b", txt)
                rec[cname] = flag(m.group(), "HIGH") if m else flag(txt, "LOW")

            elif cname == "date":
                m = re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", txt)
                rec[cname] = flag(m.group(), "HIGH") if m else flag(txt, "LOW")

            elif cname == "DF":
                m = re.search(r"\b[DF]\b", txt)
                rec[cname] = flag(m.group(), "HIGH") if m else flag(txt, "LOW")
            else:
                if txt in ["-", "–"]:
                    rec[cname] = flag("-", "HIGH")
                elif re.match(r"\d+\s*-\s*\d+", txt):
                    rec[cname] = flag(expand_range(txt), "MED")
                elif re.match(r"[\d,]+", txt):
                    rec[cname] = flag(txt.replace(" ", ""), "MED")
                else:
                    rec[cname] = flag(txt, "LOW")
        records.append(rec)

df = pd.DataFrame(records)

# Drop empty rows (no usable ID)
df = df[~df["id"].str.startswith("LOW:")]

df.to_csv(OUT_CSV, index=False)
print(f"Saved {len(df)} records to {OUT_CSV}")
