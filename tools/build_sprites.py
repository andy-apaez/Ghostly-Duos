"""Build assets/sprites.js from the art in sprites/.

Cuts every frame out of the showcase sheets at native resolution (the sheets are
upscaled 3x/4x), makes cell backgrounds transparent, packs all frames into one
atlas, cleans the boss room reference into a background plate, and writes a JS
file the game loads with a <script> tag (so it works from file://, the Node
server, or a static host).

Run from the project root:  python3 tools/build_sprites.py
"""
import base64, io, json, os, sys
from collections import Counter
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from cells import find_cells

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPR = os.path.join(ROOT, 'sprites')
OUT = os.path.join(ROOT, 'assets')

GHOST_ROWS = ['idle', 'run', 'jump', 'fall', 'dash', 'attack', 'hurt', 'death', 'slash']
MOB_NAMES = ['hex_lantern', 'arcane_slime', 'grimoire', 'shroom_mage', 'crystal_golem', 'star_moth']
MOB_ROWS = ['idle', 'move', 'attack', 'hurt', 'death', 'fx']
FX_ROWS = ['wisp_bolt', 'wisp_impact', 'thorn_spear', 'thorn_impact', 'root_snare',
           'spirit_nova', 'bramble_ring', 'haunt_fog', 'aoe_telegraph']
WRAITH_ROWS = ['idle', 'attack', 'hurt', 'death']


def cut(im, cell, scale):
    """Downscale one showcase cell to native pixels; the cell's own background becomes transparent."""
    x, y, w, h = cell
    c = im[y:y + h, x:x + w]
    bg = Counter(map(tuple, c[:, :, :3].reshape(-1, 3))).most_common(1)[0][0]
    n = c[::scale, ::scale].copy()
    n[np.all(n[:, :, :3] == bg, axis=2)] = 0
    return n


def frames_from_grid(path, size, scale=1):
    """Frames from a transparent grid sheet (forest wraith sheets); empty cells are skipped per row."""
    im = np.array(Image.open(path).convert('RGBA'))
    if scale > 1:
        im = im[::scale, ::scale]
    rows = []
    for r in range(im.shape[0] // size):
        row = []
        for c in range(im.shape[1] // size):
            f = im[r * size:(r + 1) * size, c * size:(c + 1) * size]
            if f[:, :, 3].any():
                row.append(f.copy())
        rows.append(row)
    return rows


def collect():
    anims = {}
    im, rows = find_cells(os.path.join(SPR, 'ghost_players_showcase.png'), (22, 24, 30))
    for name, row in zip(GHOST_ROWS, rows):
        anims['ghost_white.' + name] = [cut(im, c, 4) for c in row if c[0] < 830]
        anims['ghost_black.' + name] = [cut(im, c, 4) for c in row if c[0] >= 830]

    im, rows = find_cells(os.path.join(SPR, 'magic_mobs_v2_showcase.png'), (22, 24, 30))
    assert len(rows) == len(MOB_NAMES) * len(MOB_ROWS), len(rows)
    for i, mob in enumerate(MOB_NAMES):
        for j, name in enumerate(MOB_ROWS):
            anims[mob + '.' + name] = [cut(im, c, 3) for c in rows[i * len(MOB_ROWS) + j]]

    im, rows = find_cells(os.path.join(SPR, 'boss_attacks_showcase.png'), (24, 28, 30))
    for name, row in zip(FX_ROWS, rows):
        anims['fx.' + name] = [cut(im, c, 3) for c in row]

    for name, row in zip(WRAITH_ROWS, frames_from_grid(os.path.join(SPR, 'forest_wraith_spritesheet_64px.png'), 64)):
        anims['wraith.' + name] = row
    anims['wraith.stun'] = frames_from_grid(os.path.join(SPR, 'forest_wraith_stun_4x.png'), 64, 4)[0]
    return anims


# Regions (native px, x0,y0,x1,y1 exclusive) covering the characters baked into the GIF, and where to copy
# replacement background from (dx,dy offset of the source).
ROOM_PATCHES = [
    ((122, 126, 150, 160), (0, -34)),    # white ghost: in front of a trunk, copy from directly above
    ((176, 194, 207, 227), (32, 0)),     # black ghost: in front of bushes, copy from the right
    ((212, 98, 242, 154), (60, 0)),      # forest wraith (two halves): copy from the clear strip of light
    ((242, 98, 272, 154), (30, 0)),      #   rays at x 272-302, between the boss and the next trunk
]
MID_PLANK = ((208, 112, 272, 125), (320, 160, 368))   # rebuilt from the clean right-hand plank


def clean_boss_room(anims):
    """Boss room plate: per-pixel mode over the GIF frames (drops particles and flicker), then the
    baked-in characters are patched over with nearby background and the middle plank is rebuilt."""
    g = Image.open(os.path.join(SPR, 'boss_room_v2_preview.gif'))
    fr = []
    for i in range(g.n_frames):
        g.seek(i)
        fr.append(np.array(g.convert('RGB'))[::2, ::2].astype(np.int32))
    fr = np.stack(fr)
    key = (fr[..., 0] << 16) | (fr[..., 1] << 8) | fr[..., 2]
    plate = np.zeros(key.shape[1:], np.int32)
    cnt = np.zeros(key.shape[1:], np.int32)
    for k in range(key.shape[0]):
        c = (key == key[k]).sum(axis=0)
        better = c > cnt
        plate[better] = key[k][better]
        cnt[better] = c[better]
    rgb = np.stack([(plate >> 16) & 255, (plate >> 8) & 255, plate & 255], axis=2).astype(np.uint8)
    src = rgb.copy()
    for (x0, y0, x1, y1), (dx, dy) in ROOM_PATCHES:
        rgb[y0:y1, x0:x1] = src[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
    (x0, y0, x1, y1), (sx0, sy0, sx1) = MID_PLANK
    band = src[sy0:sy0 + (y1 - y0), sx0:sx1]                 # right plank, 48 wide
    cap = 8
    mid = band[:, cap:-cap]
    need = (x1 - x0) - 2 * cap
    body = np.concatenate([mid] * (need // mid.shape[1] + 1), axis=1)[:, :need]
    rgb[y0:y1, x0:x1] = np.concatenate([band[:, :cap], body, band[:, -cap:]], axis=1)
    rgb = np.concatenate([rgb[4:], rgb[-4:]], axis=0)        # shift up 4px so floors sit on the 16px grid
    a = np.full(rgb.shape[:2] + (1,), 255, np.uint8)
    return np.concatenate([rgb, a], axis=2)


def pack(anims):
    """Shelf-pack all frames into one atlas, tallest first."""
    items = [(name, i, f) for name, fs in anims.items() for i, f in enumerate(fs)]
    items.sort(key=lambda t: (-t[2].shape[0], -t[2].shape[1]))
    W = 1024
    x = y = shelf = 0
    pos = {}
    for name, i, f in items:
        h, w = f.shape[:2]
        if x + w > W:
            x, y, shelf = 0, y + shelf + 1, 0
        pos[(name, i)] = (x, y)
        x += w + 1
        shelf = max(shelf, h)
    H = y + shelf
    atlas = np.zeros((H, W, 4), np.uint8)
    meta = {}
    for name, fs in anims.items():
        rects = []
        bb = [1e9, 1e9, -1, -1]
        for i, f in enumerate(fs):
            px, py = pos[(name, i)]
            h, w = f.shape[:2]
            atlas[py:py + h, px:px + w] = f
            rects.append([px, py, w, h])
            ys, xs = np.nonzero(f[:, :, 3])
            if len(xs):
                bb = [min(bb[0], xs.min()), min(bb[1], ys.min()), max(bb[2], xs.max() + 1), max(bb[3], ys.max() + 1)]
        meta[name] = {'f': rects, 'w': fs[0].shape[1], 'h': fs[0].shape[0], 'bb': [int(v) for v in bb]}
    return atlas, meta


def png_uri(arr):
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, 'PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def main():
    anims = collect()
    atlas, meta = pack(anims)
    room = clean_boss_room(anims)
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray(atlas).save(os.path.join(OUT, 'atlas.png'))
    Image.fromarray(room).save(os.path.join(OUT, 'boss_room.png'))
    js = ('// Generated by tools/build_sprites.py from the art in sprites/. Do not edit by hand.\n'
          'window.SPRITES=' + json.dumps({'atlas': png_uri(atlas), 'room': png_uri(room), 'anims': meta},
                                         separators=(',', ':')) + ';\n')
    with open(os.path.join(OUT, 'sprites.js'), 'w') as f:
        f.write(js)
    print('atlas %dx%d, %d animations, %d frames, sprites.js %.0f KB' % (
        atlas.shape[1], atlas.shape[0], len(meta), sum(len(m['f']) for m in meta.values()), len(js) / 1024))
    for name in sorted(meta):
        m = meta[name]
        print('  %-26s %2d x %3dx%-3d  content bbox %s' % (name, len(m['f']), m['w'], m['h'], m['bb']))


if __name__ == '__main__':
    main()
