"""Cuts my Verstappen chibi drawing into layers the dashboard can animate.

    python tools/make_max_layers.py

Reads tools/max_drawing.webp (drawn on a black background) and writes to app/static/:
  max_body.png    the suit, hands and legs
  max_head.png    hair, face and ears, with the eyes and mouth painted out (the app draws those so they can move)
  max_avatar.png  the head as drawn, for the chat window
Coordinates in the app are in the drawing's own pixels, so redraw at the same size or update the numbers in polly.py.
"""
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'app', 'static')
SCALE = 0.5   # the layers are shown about 140px wide, so half size is still sharp on retina screens

img = np.array(Image.open(os.path.join(HERE, 'max_drawing.webp')).convert('RGB')).astype(int)
r, g, b = img[..., 0], img[..., 1], img[..., 2]
H, W = r.shape
yy, xx = np.mgrid[0:H, 0:W]
disk = lambda n: (np.hypot(*np.mgrid[-n:n + 1, -n:n + 1]) <= n)

# 1. the whole character: everything that is not black, with the black lines inside closed up, plus the outline
dark = (r < 45) & (g < 45) & (b < 45)
inside = ndi.binary_fill_holes(ndi.binary_closing(~dark, disk(9)))
figure = ndi.binary_dilation(inside, disk(7))

# 2. the head: skin and hair connected to the face, filled, plus its outline
skin = (r > 200) & (g > 180) & (b > 150) & (r - b > 20)
hair = (r > 90) & (r < 215) & (g > 70) & (g < 190) & (b < 140) & (r - b > 25)
blob = ndi.binary_fill_holes(ndi.binary_closing((skin | hair) & (yy < 660), disk(10)))
lab, _ = ndi.label(blob)
head_core = lab == lab[480, 430]                       # the part that holds the face
head = ndi.binary_dilation(head_core, disk(7)) & figure
head |= figure & (yy < 605)                            # everything above the shoulders goes with the head
outline = (r < 80) & (g < 80) & (b < 80)
head &= ~((yy >= 605) & ~skin & ~outline)              # suit bits next to the chin stay on the body

# 3. paint out the eyes, lids and mouth on the head so the app can draw them
face = img.copy()
skin_tone = np.median(img[skin & head_core & (yy > 520) & (yy < 600)], axis=0)
for cx, cy, rx, ry in [(322, 470, 42, 46), (537, 468, 42, 46)]:          # eye + lid
    face[((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1] = skin_tone
face[(yy >= 546) & (yy <= 570) & (xx >= 374) & (xx <= 478)] = skin_tone      # mouth

# 4. the body: the rest of the figure; under the chin it gets suit colour so a tilting head never shows a hole
body = figure & ~head
suit = (b > 90) & (r < 90) & (g < 100)
navy = np.median(img[suit & (yy > 700) & (yy < 800)], axis=0)
under_chin = head & (yy > 600) & ndi.binary_dilation(body, disk(40))
body_rgb = img.copy()
body_rgb[under_chin] = navy
body = body | under_chin

ys, xs = np.where(figure)
box = (xs.min() - 4, ys.min() - 4, xs.max() + 5, ys.max() + 5)


def save(rgb, mask, name, crop=box):
    alpha = (ndi.gaussian_filter(mask.astype(float), 0.7) * 255).clip(0, 255).astype(np.uint8)
    out = Image.fromarray(np.dstack([rgb.clip(0, 255).astype(np.uint8), alpha])).crop(crop)
    out = out.resize((round(out.width * SCALE), round(out.height * SCALE)), Image.LANCZOS)
    out.save(os.path.join(OUT, name), optimize=True)
    return out.size


os.makedirs(OUT, exist_ok=True)
print('box', box)
print('body', save(body_rgb, body, 'max_body.png'))
print('head', save(face, head, 'max_head.png'))
hy, hx = np.where(head)
side = max(hx.max() - hx.min(), hy.max() - hy.min()) + 20
cx, cy = (hx.min() + hx.max()) // 2, (hy.min() + hy.max()) // 2
avatar_box = (cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)
print('avatar', save(img, head, 'max_avatar.png', avatar_box))
print('skin', skin_tone.round(), 'navy', navy.round())
