import io
import math
import os
import sys

import pymupdf
from fontTools import ttLib

import dmc
import haed

font_size = 15
ROWS_PER_COL = 26

script_dir = os.path.dirname(os.path.abspath(__file__))

def make_card(pattern_name, threads, fonts):
    PAGE_W, PAGE_H = 612, 792
    MARGIN = 36
    GUTTER = 12
    COL_W = (PAGE_W - 2*MARGIN - GUTTER) // 2  # 264 pts
    ROW_H = 27
    HEADER_H = 30
    Y_START = MARGIN
    Y_DATA = Y_START + HEADER_H
    Y_END = PAGE_H - MARGIN
    ROWS_PER_COL = (Y_END - Y_DATA) // ROW_H   # ~21
    COL_X = [MARGIN, MARGIN + COL_W + GUTTER]
    SUB_COLS = [40, 48, 88, 48, 40]            # swatch|sym|dmc|sym|swatch, sum=264

    # Distribute items evenly across columns (matches original intent)
    items = sorted(threads, key=lambda v: (int(''.join(filter(str.isdigit, str(v[2]))))))
    n = len(items)
    total_cols = math.ceil(n / ROWS_PER_COL)
    rows_per_col = math.ceil(n / total_cols) if total_cols else ROWS_PER_COL

    doc = pymupdf.open()

    def new_page():
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        for k in fonts:
            page.insert_font(fontname=k, fontbuffer=fonts[k][1])

        # Draw both column headers
        for ci in range(2):
            x0 = COL_X[ci]
            r = pymupdf.Rect(x0, Y_START, x0 + COL_W, Y_START + HEADER_H)
            page.draw_rect(r, color=(0, 0, 0), width=0.5)
            page.insert_textbox(r, pattern_name, fontsize=font_size,
                                align=pymupdf.TEXT_ALIGN_CENTER)
        return page

    def draw_row(page, col_idx, row_idx, symbol_bytes, font_xref, color, dmc_id, is_even):
        x0 = COL_X[col_idx]
        y0 = Y_DATA + row_idx * ROW_H
        # Build sub-column rects
        xs = []
        cx = x0
        for w in SUB_COLS:
            xs.append(cx)
            cx += w
        rects = [pymupdf.Rect(xs[i], y0, xs[i] + SUB_COLS[i], y0 + ROW_H)
                 for i in range(5)]

        ttf = fonts[font_xref]

        if is_even:
            rects.reverse()

        for r in rects[:3]:
            page.draw_rect(r, color=(0, 0, 0), width=0.5)

 
        r = ttf[2].glyph_bbox(ord(symbol))
        h = (r[3] - r[1]) * font_size
        rects[1][1] += (ROW_H - h - 4) / 2
        page.draw_rect(rects[0], fill=color, color=None, width=0)
        page.insert_textbox(rects[1], symbol, fontname=font_xref,
                            fontsize=font_size, align=pymupdf.TEXT_ALIGN_CENTER)
        page.insert_textbox(rects[2], str(dmc_id), fontsize=font_size,
                            align=pymupdf.TEXT_ALIGN_CENTER)

    page = new_page()
    col, row = 0, 0

    for i, item in enumerate(items):
        (symbol, font, dmc_id) = item

        if row >= rows_per_col:
            row = 0
            col += 1
            if col > 1:
                col = 0
                page = new_page()

        color = dmc.dmc[dmc_id][1]
        draw_row(page, col, row, symbol, font, color, dmc_id, i % 2 == 0)
        row += 1

    return doc

def make_card_from_stream(stream):
    chart = pymupdf.open(stream=stream)
    if len(chart[0].get_text('dict')['blocks']) == 1:
        return (None, "chart is not HAED or is modified")
    text = chart[0].get_text()
    title = ''
    if not text.startswith("Heaven and Earth Designs"):
        return (None, "chart is not HAED or is modified")

    start_line = 1 # 0 is HAED title
    lines = text.split('\n')
    if lines[1] == 'For ':
        start_line += 2
    for line in lines[start_line:]:
        line = line.strip()
        if line.startswith("Custom Chart"):
            break
        if line.startswith("Chart"):
            break
        if line.startswith("By Michele Sayetta"):
            break
        if line.startswith("("):
            break
        title += line + ' '
    pattern_name = title.strip()
    (threads, fonts) = haed.extract_legend(chart)
    doc = make_card(pattern_name, threads, fonts)
    pattern_name = pattern_name.replace(' ','_')
    return (doc, pattern_name)

if __name__ == "__main__":
    in_file = sys.argv[1] 
    with open(in_file, 'rb') as stream:
        (doc, pattern_name) = make_card_from_stream(stream.read())
    if doc is None:
        print(pattern_name)
        exit(1)
    print(f"{pattern_name}-card.pdf")
    doc.save(f"{pattern_name}-card.pdf")
