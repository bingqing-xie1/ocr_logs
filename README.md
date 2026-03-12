# ocr_logs
Segment and perform ocr on logs

# Pre-requisite
Install poppler (https://poppler.freedesktop.org/) for PDF loading and Tesseract-OCR (https://github.com/tesseract-ocr/tesseract) for character recognization (does not perform well on this set of hand-writing images).

# Prefix path and library
PDF_PRE='Your/dir/for/logs'
PDF_PATH = "combined.pdf"
POPPLER_PATH = r"C:\poppler\Library\bin"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Fixed header
Right now, it assumes the fixed structured of "id", "date", "DF", "B9", "T", "DMSO_F"
If the header doesn't match, the order and label need to be adjusted.

# Output
Saved each grid into a row_col.png image and the OCR results in text file.
