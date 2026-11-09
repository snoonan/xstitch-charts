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


def show_lines(doc):
    for page in doc:
        text = page.get_text('dict')
        print(text['blocks'][0]['lines'][0]['spans'][0]['text'])
        for b in text['blocks']:
            if 'lines' not in b:
                print(f" no lines")
                continue
            print(f" {len(b['lines'])} {list((len(l['spans'][0]['text']) for l in b['lines']))}")
            print(f" {len(b['lines'])} {list((l['spans'][0]['text']) for l in b['lines'])}")

def make_image_from_stream(stream):
    (chart, pattern_name) = haed.open_chart(stream)
    if chart is None:
        return (chart, pattern_name)
    show_lines(chart)
    pattern_name = pattern_name.replace(' ','_')
    return (None, pattern_name)

if __name__ == "__main__":
    in_file = sys.argv[1] 
    with open(in_file, 'rb') as stream:
        (doc, pattern_name) = make_image_from_stream(stream.read())
    if doc is None:
        print(pattern_name)
        exit(1)
    print(f"{pattern_name}-image.jpg")
