import io
import math
import os
import sys

import pymupdf
from fontTools import ttLib

from PIL import Image, ImageDraw

import dmc
import haed

STITCH = 10
STITCH_WIDTH = 3
STITCH_GAP = 1

def make_image(pattern_name, grid):
    width = max((len(r) for r in grid)) * STITCH
    height = len(grid) * STITCH

    doc = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(doc)
    for r in range(len(grid)):
        for c, symbol in enumerate(grid[r]):
            if symbol[0] is None:
                # background in a no background chart
                continue
            color = tuple((int(c * 255) for c in dmc.dmc[symbol[2]][1]))
            draw.line(((c*STITCH + STITCH_GAP,r*STITCH + STITCH_GAP, (c+1)*STITCH - STITCH_GAP,(r+1)*STITCH - STITCH_GAP)), color, STITCH_WIDTH)
            draw.line((((c+1)*STITCH - STITCH_GAP,r*STITCH + STITCH_GAP, (c)*STITCH + STITCH_GAP,(r+1)*STITCH - STITCH_GAP)), color, STITCH_WIDTH)
    return doc

def make_image_from_stream(stream):
    (chart, pattern_name) = haed.open_chart(stream)
    if chart is None:
        return (chart, pattern_name)
    (threads, _) = haed.extract_legend(chart)
    grid = haed.extract_grid(chart, threads)
    if len(grid) == 0:
        return (None, 'No grid found')
    doc = make_image(pattern_name, grid)
    pattern_name = pattern_name.replace(' ','_')
    return (doc, pattern_name)

if __name__ == "__main__":
    in_file = sys.argv[1] 
    with open(in_file, 'rb') as stream:
        (doc, pattern_name) = make_image_from_stream(stream.read())
    if doc is None:
        print((in_file,pattern_name))
        exit(1)
    print(f"{pattern_name}-image.jpg")
    doc.save(f"{pattern_name}-image.jpg")
