import io
import math
import os
import sys

import pymupdf
from fontTools import ttLib

from PIL import Image, ImageDraw

import dmc

HAED_OVERLAP = 3

script_dir = os.path.dirname(os.path.abspath(__file__))
def add_to_font(fonts, font, symbol):
    src = fonts[font][2]
    try:
        rcmap = src['cmap'].buildReversed()
    except (TypeError, KeyError, AssertionError):
        return
    merge = fonts[font][3]
    try:
        g = src['cmap'].getBestCmap()[ord(symbol)]
    except (TypeError, KeyError):
        return
    if g in merge['glyf']:
        return
    glyph_id = src.getGlyphID(g)
    cmap_id = rcmap[g].pop() # use first option

    merge['glyf'][g] = src['glyf'][g]
    merge['hmtx'].metrics[g] = src['hmtx'].metrics[g]
    merge['cmap'].getBestCmap()[cmap_id] = g
    new_cmap_set = set(merge['cmap'].getBestCmap().items())
    cmap_set = new_cmap_set
    fonts[font][0] = True
    return

def parse_symbol(span, state):
                    symbol = span['text']
                    font = span['font']
                    font.replace('/','')

                    state['symbol'] = symbol
                    state['font'] = font
                    return state

def parse_dmc(span):
                    dmc = span['text']
                    dmc = dmc.replace('DMC','').strip()
                    if dmc == '':
                        return None
                    if not dmc.isnumeric():
                        return dmc.lower()
                    dmc = int(dmc)
                    return dmc

def remember_font(fonts, font, doc, cleaned_fonts):
                        _, _, _,  buffer = doc.extract_font(cleaned_fonts[font][0])
                        # font I dont have (yet)
                        fonts[font] = [True, buffer,  pymupdf.Font(fontbuffer=buffer)]


def parse_dmc_blocks(dmc_blocks, threads, fonts, doc, cleaned_fonts):
            state = {'skip': 0, 'symbol': None, 'font': None}
            y = 0
            for line in (l for b in dmc_blocks for l in b['lines']):
                if line['bbox'][1] > y:
                    y = line['bbox'][3]
                    state = {'skip': 0, 'symbol': None, 'font': None}
                if state['skip']:
                    state['skip'] = 0
                    continue
                if state['symbol'] is None:
                    parse_symbol(line['spans'][0], state)
                    if state['font'] not in fonts:
                        remember_font(fonts, state['font'], doc, cleaned_fonts)
                    state['skip'] = 1
                else:
                    dmc = parse_dmc(line['spans'][0])
                    if dmc is None:
                        continue
                    state['skip'] = 1
                    threads.append((state['symbol'], state['font'], dmc))
                    state['symbol'] = None

def extract_legend(doc):
    threads = []
    fonts = {}

    for page in doc:
        extracted_fonts = page.get_fonts(full=True)
        cleaned_fonts = {font_name: (font_id, font_format, font_type, font_flags, font_encoding, font_embedded) for font_id, font_format, font_type, font_name, font_flags, font_encoding, font_embedded in extracted_fonts}
        cleaned_fonts.update({font_name.split('+')[-1]: (font_id, font_format, font_type, font_flags, font_encoding, font_embedded) for font_id, font_format, font_type, font_name, font_flags, font_encoding, font_embedded in extracted_fonts if "+" in font_name})
        if 'Symbol' in page.get_text():
            blocks = page.get_text('dict')['blocks']
            start_of_threads = list((b['lines'][0]['spans'][0]['text'] for b in blocks)).index('Symbol') 
            parse_dmc_blocks(blocks[start_of_threads + 1:], threads, fonts, doc, cleaned_fonts)

    return (threads, fonts)

def find_grid_spacing(text):
    # Test if this is a grid page, they have row numbers as the last block
    try:
        if text['blocks'][-1]['lines'][0]['spans'][0]['font'].startswith("Cross"):
            return None
        int(text['blocks'][-1]['lines'][0]['spans'][0]['text'])
        int(text['blocks'][-1]['lines'][1]['spans'][0]['text'])
    except (KeyError,ValueError,IndexError):
        return None

    # find first grid number on axis (h and v)
    x1 = text['blocks'][-2]['lines'][0]['spans'][0]['bbox']
    x2 = text['blocks'][-2]['lines'][1]['spans'][0]['bbox']
    y1 = text['blocks'][-1]['lines'][0]['spans'][0]['bbox']
    y2 = text['blocks'][-1]['lines'][1]['spans'][0]['bbox']

    # get first marker text (as int)
    x1t = text['blocks'][-2]['lines'][0]['spans'][0]['text']
    y1t = text['blocks'][-1]['lines'][0]['spans'][0]['text']
    x1t = int(x1t)
    y1t = int(y1t)

    # get center point of number (shouldbe vdery close to lines)
    xx1 = x1[2] - x1[0]
    xx2 = x2[2] - x2[0]
    xx1 = xx1 / 2 + x1[0]
    xx2 = xx2 / 2 + x2[0]
    yy1 = y1[3] - y1[1]
    yy2 = y2[3] - y2[1]
    yy1 = yy1 / 2 + y1[1]
    yy2 = yy2 / 2 + y2[1]

    # size of grid square
    xdelta = (xx2-xx1) / 10
    ydelta = (yy2-yy1) / 10

    # top left corner
    xbase = y1[2]
    ybase = x1[3]


    return (xdelta, ydelta, xbase, ybase)

def find_grid_offset(text, xdelta, ydelta, xbase, ybase):
    xblock = -2
    yblock = -1
    gridblock = -3

    if text['blocks'][-1]['lines'][0]['dir'] == (1.0, 0.0):
        # one block, but it is x not y
        xblock = -1
        yblock = None

    x1 = text['blocks'][xblock]['lines'][0]['spans'][0]['bbox']
    if yblock:
        # find first grid number on axis (h and v)
        y1 = text['blocks'][yblock]['lines'][0]['spans'][0]['bbox']

        # get first marker text (as int)
        y1t = text['blocks'][yblock]['lines'][0]['spans'][0]['text']
        y1t = int(y1t)

        # get center point of number (shouldbe vdery close to lines)
        yy1 = y1[3] - y1[1]
        yy1 = yy1 / 2 + y1[1]

        # top left row.column in grid
        ytop = round(y1t - (yy1 - ybase)/ ydelta)
    else:
        ytop = None
        gridblock = gridblock + 1

    try:
        # get first marker text (as int)
        x1t = text['blocks'][xblock]['lines'][0]['spans'][0]['text']
        x1t = int(x1t)

        # get center point of number (shouldbe vdery close to lines)
        xx1 = x1[2] - x1[0]
        xx1 = xx1 / 2 + x1[0]

        # top left row.column in grid
        xleft = round(x1t - (xx1 - xbase)/ xdelta)
    except ValueError:
        xleft = None
        gridblock = gridblock + 1

    lines = text['blocks'][gridblock]['lines']
    if (lines[0]['spans'][0]['bbox'][0] < xbase or 
       lines[0]['spans'][0]['bbox'][1] < ybase):
           lines = []
    return (xleft, ytop, lines)

def extract_grid(doc, threads):
    grid = []

    by_symbol = {v[0]: v for v in threads}
    xdelta = None
    ydelta = None
    xleft = None
    ytop = None

    for page in doc:
        text = page.get_text('dict')
        if xdelta is None:
            spacing = find_grid_spacing(text)
            if spacing is not None:
                (xdelta, ydelta, xbase, ybase) = spacing
            else:
                continue

        last_top = ytop
        last_left = xleft
        (xleft, ytop, lines) = find_grid_offset(text, xdelta, ydelta, xbase, ybase)
        if xleft is None:
            # right edge, so same top as last page, left as largest on last page, (May fail on no background with isolated part)
            ytop = last_top
            xleft = max((len(r) for r in grid[ytop:])) - HAED_OVERLAP
        if ytop is None:
            # bottom row, either first page (left is less than width of grid) or continuing last pages row
            if xleft <= max((len(r) for r in grid[ytop:])):
                ytop = len(grid)
            else:
                ytop = last_top

        for i, line in enumerate(lines):
            if line['spans'][0]['color'] != 0:
                continue
            symbols = line['spans'][0]['text']
            symbols = symbols.replace(' ','')
            grid_items = [by_symbol[s] for s in symbols]
            coord = line['spans'][0]['bbox']
            c = round((coord[0] - xbase) / xdelta) + xleft
            r = round((coord[1] - ybase) / ydelta) + ytop
            
            #print(f"{r} {c} {len(symbols)}")
            if r >= len(grid):
                grid.extend(map(lambda x:list(), range(r-len(grid)+1)))
            if c > len(grid[r]):
                grid[r].extend(map(lambda x:(None, None, None), range(c-len(grid[r]))))
            grid[r].extend(grid_items)

    return grid

def open_chart(stream):
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
    return (chart, pattern_name)
