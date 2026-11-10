"""Contact sheets (4x4, in capture order, labelled) of the BFTest_*.png shots in a folder."""
import sys, glob, os
from PIL import Image, ImageDraw
d = sys.argv[1]
files = sorted(glob.glob(os.path.join(d, "BFTest_*.png")), key=os.path.getmtime)
for p in range(0, len(files), 16):
    chunk = files[p:p + 16]
    rows = (len(chunk) + 3) // 4
    W = Image.new("RGB", (480 * 4, 270 * rows))
    dr = ImageDraw.Draw(W)
    for i, f in enumerate(chunk):
        W.paste(Image.open(f).convert("RGB").resize((480, 270)), ((i % 4) * 480, (i // 4) * 270))
        dr.text(((i % 4) * 480 + 4, (i // 4) * 270 + 4), os.path.basename(f)[7:-4], fill=(255, 255, 0))
    out = os.path.join(d, "sheet_%d.png" % (p // 16))
    W.save(out)
    print(out)
