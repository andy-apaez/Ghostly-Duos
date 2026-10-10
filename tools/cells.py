"""Find the frame cells in a showcase sheet: solid rectangles that differ from the page background."""
from PIL import Image
import numpy as np
from scipy import ndimage

def find_cells(path, page_bg, min_size=40):
    im = np.array(Image.open(path).convert('RGBA'))
    mask = np.any(im[:, :, :3] != np.array(page_bg), axis=2)
    lab, n = ndimage.label(mask)
    cells = []
    for sl in ndimage.find_objects(lab):
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        if (x1 - x0) >= min_size and (y1 - y0) >= min_size:
            cells.append((x0, y0, x1 - x0, y1 - y0))
    cells.sort(key=lambda c: (c[1], c[0]))
    rows = []
    for c in cells:  # group into rows by top edge
        if rows and abs(rows[-1][0][1] - c[1]) < 8: rows[-1].append(c)
        else: rows.append([c])
    return im, rows
