import math
import os
import sys

import pymupdf

import dmc

font_size = 15
ROWS_PER_COL = 26

def extract_legend(doc):
    threads = []
    for page in doc:
        if 'Symbol' in page.get_text():
            y = 0
            symbol = None
            font = None
            skip = 0
            for line in page.get_text('dict')['blocks'][-1]['lines']:
                if line['bbox'][1] > y:
                    y = line['bbox'][3]
                    skip = 0
                    symbol = None
                if skip:
                    skip = 0
                    continue
                if symbol is None:
                    symbol = line['spans'][0]['text']
                    font = line['spans'][0]['font']
                    skip = 1
                else:
                    dmc = line['spans'][0]['text']
                    dmc = dmc.replace('DMC','')
                    if not dmc.strip().isnumeric():
                        continue
                    dmc = int(dmc)
                    skip = 1
                    threads.append((symbol, font, dmc))

    return threads

def make_card(pattern_name, threads):
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

    # Resolve font files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fallback_candidates = [
        os.path.join(script_dir, 'DejaVuSansMono.ttf'),
        os.path.join(script_dir, '..', 'scripts', 'DejaVuSansMono.ttf'),
    ]
    fallback_font = next((p for p in fallback_candidates if os.path.exists(p)), None)

    font_files = {}
    for (_, f, _) in threads:
        if f in font_files:
            continue
        ttf = f"{f}.ttf"
        if os.path.exists(ttf):
            pass
        elif os.path.exists(os.path.join(script_dir,ttf)):
            ttf = os.path.join(script_dir,ttf)
        elif fallback_font:
            print(f"Missing {ttf}, using fallback")
            ttf = fallback_font
        else:
            print(f"Missing {ttf} and no fallback found")
            ttf = None
        font_files[f] = (ttf, pymupdf.Font(fontfile=ttf))

    # Distribute items evenly across columns (matches original intent)
    items = sorted(threads, key=lambda v: int(v[2]))
    n = len(items)
    total_cols = math.ceil(n / ROWS_PER_COL)
    rows_per_col = math.ceil(n / total_cols) if total_cols else ROWS_PER_COL

    doc = pymupdf.open()

    def new_page():
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
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

        ttf = font_files[font_xref]

        if is_even:
            rects.reverse()

        for r in rects[:3]:
            page.draw_rect(r, color=(0, 0, 0), width=0.5)

 
        r = ttf[1].glyph_bbox(ord(symbol))
        h = (r[3] - r[1]) * font_size
        rects[1][1] += (ROW_H - h - 4) / 2
        page.draw_rect(rects[0], fill=color, color=None, width=0)
        page.insert_textbox(rects[1], symbol, fontfile=ttf[0], fontname=os.path.basename(ttf[0][:-4]),
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

def create_card(threads):
    items = sorted(thread_map.items(), key=lambda v: int(v[1][3]))
    n = len(items)
    total_cols = math.ceil(n / ROWS_PER_COL)
    rows_per_col = math.ceil(n / total_cols) if total_cols else ROWS_PER_COL

    doc = pymupdf.open()

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

        color = dmc.dmc[dmc_id]
        draw_row(page, col, row, symbol, font_xref, color, dmc, i % 2 == 0)
        row += 1

    return doc

def make_card_from_stream(stream):
    chart = pymupdf.open(stream=stream)
    if len(chart[0].get_text('dict')['blocks']) == 1:
        print("chart is not HAED or is modified")
        return None
    text = chart[0].get_text()
    title = ''
    if not text.startswith("Heaven and Earth Designs"):
        print("chart is not HAED or is modified")
        return None

    for line in text.split('\n')[1:]: # 0 is HAED title
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
    threads = extract_legend(chart)
    doc = make_card(pattern_name, threads)
    pattern_name = pattern_name.replace(' ','_')
    return (doc, pattern_name)

if __name__ == "__main__":
    in_file = sys.argv[1] 
    with open(in_file, 'rb') as stream:
        (doc, pattern_name) = make_card_from_stream(stream)
    doc.save(f"{pattern_name}-card.pdf")

