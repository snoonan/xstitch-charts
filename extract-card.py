from enum import Enum
import os
import sys
import argparse

from pypdf.generic import DecodedStreamObject, EncodedStreamObject
from pypdf import PdfReader, PdfWriter
import pypdf

from fpdf import FPDF
from fpdf.fonts import FontFace

font_size = 15
class state(Enum):
    SCAN_FOR_ENTRY = 0,
    GET_COLOR = 1,
    GET_SYMBOL = 2,
    GET_DMC = 3,

next_symbol = 42
mapping = {}

def parse_page(operations, fonts):
    global next_symbol
    symbol_page  = False
    for i,op in enumerate(operations):
        if op[-1] == b'Tj' and 'Strands' in op[0]:
            symbol_page = True
            entry_state = state.SCAN_FOR_ENTRY
        if not symbol_page:
            """ find Tj, replace all after TT4 with replacement dice """
            if op[-1] == b'Tf':
                pending_font = op[0]
            
        else: # Symbol page
            if entry_state == state.SCAN_FOR_ENTRY:
                if op[-1] == b'cs':
                    entry_state = state.GET_COLOR
                    continue
            if entry_state == state.GET_COLOR:
                if op[-1] == b'scn':
                    pending_color = op[0]
                    entry_state = state.GET_SYMBOL
                    continue
            if entry_state == state.GET_SYMBOL:
                if op[-1] == b'Tf':
                    pending_font = fonts[op[0][0]]
                    continue
                if op[-1] == b'Tj':
                    sym = op[0][0].original_bytes
                    try:
                        symg = op[0][0].get_original_bytes()
                        if sym != sym2:
                            print(f"diff! {sym!r} {sym2!r}")
                    except:
                        pass
                    pending_symbol = (sym, next_symbol)
                    #operations[i] = ([pypdf.generic.TextStringObject(chr(next_symbol))], op[1])
                    next_symbol += 1
                    entry_state = state.GET_DMC
                    continue
            if entry_state == state.GET_DMC:
                if op[-1] == b'TJ':
                    strings = op[0][0][::-2] # ends with a string, every other item is an offset
                    for s in strings:
                        try:
                            int(s)
                            dmc = s
                            break
                        except ValueError:
                            pass
                    mapping[(pending_symbol[0], pending_font)] = (pending_symbol[1], pending_font, pending_color, dmc)
                    entry_state = state.SCAN_FOR_ENTRY
                    continue
    return operations

def card(in_file):
    reader = PdfReader(in_file)

    fonts = {}

    for page in reader.pages:
        objs = page.get_object()
        for obj in objs['/Resources']:
            if obj != '/Font':
                continue
            font_objs = objs['/Resources']['/Font']
            for f in font_objs:
                font_obj = font_objs[f]
                fn = font_obj['/BaseFont'][1:]
                fonts[f] = font_objs.raw_get(f).idnum

        contents = page.get_contents()

        if isinstance(contents, DecodedStreamObject) or isinstance(contents, EncodedStreamObject):
            operations = contents.operations
            contents.operations = parse_page(operations, fonts)

        elif len(contents) > 0:
            for obj in contents:
                if isinstance(obj, DecodedStreamObject) or isinstance(obj, EncodedStreamObject):
                    streamObj = obj.getObject()
                    operations = streamObj.operations
                    streamObj.operations = parse_page(operations, fonts)

    used_fonts = {}
    for m in mapping:
        (_, font,  _, _) = mapping[m]
        font_obj = reader.get_object(font)
        fn = font_obj['/BaseFont'][1:]
        used_fonts[font] = fn

    for f in used_fonts:
        font_obj = reader.get_object(f)
        if '/DescendantFonts' in font_obj:
            font_obj = font_obj['/DescendantFonts'][0] # Guess, take the first one
        if '/FontDescriptor' not in font_obj:
            continue
        if '/FontFile2' not in font_obj['/FontDescriptor']:
            continue
        fn = used_fonts[f]
        with open(f"{fn}.ttf", "wb") as fh:
            fh.write(font_obj['/FontDescriptor']['/FontFile2'].get_data())

    filename_base = os.path.splitext(os.path.basename(in_file))[0]
    doc = {"name": filename_base,
           "fonts": used_fonts,
           "map": mapping,
           }
    return doc


class MultiColumnPDF(FPDF):
    def __init__(self, *args, title, items_per_col, **kwargs):
        super().__init__(*args, **kwargs)
        self.col = 0
        self.y0 = None
        self.title = title
        self.items_per_col = items_per_col + 2 # for header
        self.items_in_col = 0
        self.item_partial = 0
        self.last_y = 0

    @property
    def accept_page_break(self):
        if self.col < 1:
            self.col += 1
            x = 10 + self.col * (self.w // 2)
            self.set_left_margin(x)
            self.set_x(x)
            self.set_y(self.y0)
            self.header()
            return False
        else:
            self.col = 0
            x = 10 + self.col * (self.w // 2)
            self.set_left_margin(x)
            self.set_x(x)
            return True

    def header(self):
        if self.y0 == None:
            self.y0 = self.y
        self.set_font("Times", size=font_size)
        self.cell(None, 10, self.title, border=1, align="C")
        # Performing a line break:
        self.ln(20)

    def will_page_break(self, height: float) -> bool:
        if self.last_y == self.y:
            return False
        self.last_y = self.y
        self.items_in_col += 1
        adjust = 0
        if self.item_partial:
            adjust = self.item_partial + .125
        #print(f'{self.items_in_col=} {self.item_partial=} {adjust=} {self.items_per_col=}')
        if self.items_in_col <= self.items_per_col + adjust:
            return False
        print(f'wrap {self.items_in_col-3=}')
        self.item_partial += self.items_per_col - self.items_in_col + 1
        self.items_in_col = 0
        return self.accept_page_break


def make_card(mapping):
    thread_map = mapping['map']
    items_per_col = 21 # counted
    items = len(thread_map.keys())
    pages = (items + items_per_col - 1) // items_per_col
    items_per_col = items / pages
    print(f"{items=} {pages=} {items_per_col=}")


    #  AAFEHI+CrossStitch3.ttf  CBAGFL+CrossStitch3.ttf  HMGBEE+CrossStitch3.ttf  KPFCFP+CrossStitch2.ttf  MHBEMG+CrossStitch2.ttf
    pdf = MultiColumnPDF(format="letter", title=mapping['name'], items_per_col=items_per_col)
    pdf.add_page()
    for f in mapping['fonts']:
        if "CrossStitch3" in mapping['fonts'][f]:
            pass
            #mapping['fonts'][f] = "../scripts/CrossStitch3"
        try:
            pdf.add_font(f"/T{f}", fname=f"{mapping['fonts'][f]}.ttf")
        except FileNotFoundError:
            print(f"Missing {mapping['fonts'][f]}")
            pdf.add_font(f"/T{f}", fname=f"../scripts/DejaVuSansMono.ttf")
        except KeyError:
            print(f"Failed to load {mapping['fonts'][f]}")
            pdf.add_font(f"/T{f}", fname=f"../scripts/DejaVuSansMono.ttf")


    pdf.set_font("Times", size=font_size)
    with pdf.table(align = "L", width = pdf.w // 2 - 20) as table:
        row = table.row()
        row.cell("Color")
        row.cell("Sym")
        row.cell("DMC")
        row.cell("Sym")
        row.cell("Color")
        for (i, ((symbol, font), item)) in enumerate(sorted(thread_map.items(), key=lambda v: int(v[1][3]))):

            row = table.row()
            (_, font, color, dmc) = item
            style = FontFace(fill_color = [255 * c for c in color])
            if i % 2 == 0:
                row.cell()
                row.cell()
                row.cell(dmc, align="C")
                row.cell(symbol.decode('cp1252', errors="ignore"), align="C", style=FontFace(f"/T{font}"))
                row.cell(" ", style=style)
            else:
                row.cell(" ", style=style)
                row.cell(symbol.decode('cp1252', errors="ignore"), align="C", style=FontFace(f"/T{font}"))
                pdf.set_font("Times", size=font_size)
                row.cell(dmc, align="C")
                row.cell()
                row.cell()

    print(f'wrap {pdf.items_in_col-3=}')
    pdf.output(f'{mapping['name']}-card.pdf')


if __name__ == "__main__":
    in_file = sys.argv[1]
    make_card(card(in_file))

