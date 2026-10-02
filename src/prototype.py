from __future__ import annotations

import math
import subprocess
from pathlib import Path

import soundfile as sf
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

from tts import generate_narration

W, H = 1080, 1920
FPS = 30
BG = (246, 240, 225)
INK = (30, 34, 40)
BLUE = (52, 117, 217)
PALE_BLUE = (214, 232, 255)
CORAL = (233, 100, 82)
PALE_CORAL = (255, 224, 216)
YELLOW = (246, 198, 69)
WHITE = (255, 255, 255)


def font(size: int, bold: bool = False):
    names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in names:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def clamp01(x):
    return max(0.0, min(1.0, x))


def ease(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def paper_texture(img):
    d = ImageDraw.Draw(img)
    for y in range(0, H, 30):
        d.line((0, y, W, y), fill=(130, 118, 95, 18), width=1)


def center_text(d, text, y, size, fill=INK, bold=True):
    f = font(size, bold)
    box = d.textbbox((0, 0), text, font=f)
    d.text(((W - (box[2]-box[0]))//2, y), text, font=f, fill=fill)


def arrow(d, x1, y1, x2, y2, fill=BLUE, width=18):
    d.line((x1,y1,x2,y2), fill=fill, width=width)
    a = math.atan2(y2-y1, x2-x1)
    L = 32
    for delta in (2.55, -2.55):
        d.line((x2,y2,x2 + L*math.cos(a+delta), y2 + L*math.sin(a+delta)), fill=fill, width=width)


def brand(d):
    d.text((50, 42), "PAPER KNOWLEDGE", font=font(32, True), fill=(92, 93, 95))


def caption_chip(d, text, y, accent=None):
    f = font(56, True)
    box = d.textbbox((0,0), text, font=f)
    tw, th = box[2]-box[0], box[3]-box[1]
    x = (W-tw)//2
    if accent:
        d.rounded_rectangle((x-20,y-12,x+tw+20,y+th+18), 20, fill=accent)
    d.text((x,y), text, font=f, fill=INK)


def coast(d):
    pts = [(760,370),(725,500),(755,625),(710,760),(742,895),(700,1030),(735,1160),(700,1290),(750,1450)]
    d.line(pts, fill=INK, width=18)
    d.text((784,390),"EAST COAST",font=font(34,True),fill=INK)


def owl_card(img, idx, x, y, w=360, h=310, angle=-4):
    poses = sorted(Path("assets/mascot").glob("pose*.png"))
    if not poses:
        return
    src = Image.open(poses[idx % len(poses)]).convert("RGB")
    crop = ImageOps.fit(src, (w,h), method=Image.Resampling.LANCZOS, centering=(0.50,0.52)).convert("RGBA")

    card = Image.new("RGBA",(w+34,h+34),(255,255,255,0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((7,7,w+27,h+27),22,fill=(255,252,242,255),outline=(31,35,40,255),width=7)
    card.alpha_composite(crop,(17,17))

    card = card.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(0,0,0,0))
    shadow = Image.new("RGBA", card.size, (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((18,22,card.width-8,card.height-4),24,fill=(0,0,0,45))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    layer = Image.new("RGBA", img.size, (0,0,0,0))
    layer.alpha_composite(shadow,(x+8,y+10))
    layer.alpha_composite(card,(x,y))
    img.alpha_composite(layer)


def hook_scene(img, t):
    d = ImageDraw.Draw(img)
    brand(d)
    center_text(d, "WHY SO WINDY?", 135, 82, BLUE)

    coast(d)

    # fast moving paper wind ribbons
    for i, yy in enumerate((500,680,860,1040,1220)):
        phase = (t*340 + i*170) % 960
        x = -260 + phase
        d.arc((x, yy-90, x+470, yy+100), 188, 352, fill=BLUE, width=24)

    # visual consequence: bent tree
    d.line((900,1200,842,1515), fill=(104,77,55), width=30)
    for yy in (1280,1360,1440):
        d.line((875,yy,770,yy-70),fill=(78,123,66),width=27)

    owl_card(img,0,70,1030,w=390,h=330,angle=-5)
    caption_chip(d, "WALL-LIKE WINDS", 1510, YELLOW)


def cold_scene(img, t):
    d = ImageDraw.Draw(img)
    brand(d)
    center_text(d, "COLD AIR RUSHES SOUTH", 145, 62, BLUE)

    # simplified Canada paper shape + falling arrows
    d.rounded_rectangle((120,360,880,800),60,fill=PALE_BLUE)
    d.text((190,470),"CANADA",font=font(82,True),fill=BLUE)
    for i in range(4):
        yy = 820 + int(((t*420 + i*155) % 520))
        arrow(d, 310+i*120, yy-140, 310+i*120, yy, BLUE, 18)

    owl_card(img,1,620,1040,w=330,h=285,angle=4)
    caption_chip(d, "COLD CANADIAN AIR", 1480, PALE_BLUE)


def ocean_scene(img, t):
    d = ImageDraw.Draw(img)
    brand(d)
    center_text(d, "THE ATLANTIC IS MILDER", 145, 62, CORAL)

    # warm ocean band slides in from right
    x0 = int(260 - 120*ease(t))
    d.rounded_rectangle((x0,420,1040,1220),60,fill=PALE_CORAL)
    d.text((x0+120,560),"ATLANTIC",font=font(78,True),fill=CORAL)
    for i in range(5):
        x = x0+130+i*120
        y = 830 + int(28*math.sin((t*6)+(i*0.7)))
        d.arc((x-40,y-20,x+120,y+75),180,360,fill=CORAL,width=15)

    # blue air enters from left to make collision readable
    arrow(d,150,960,460,960,BLUE,24)
    arrow(d,900,960,590,960,CORAL,24)
    pulse = 45 + 55*abs(math.sin(t*math.pi))
    d.ellipse((540-pulse,960-pulse,540+pulse,960+pulse),outline=YELLOW,width=18)

    owl_card(img,2,80,1060,w=350,h=295,angle=-3)
    caption_chip(d, "COLD + MILD", 1470, YELLOW)


def pressure_scene(img, t):
    d = ImageDraw.Draw(img)
    brand(d)
    center_text(d, "PRESSURE LINES TIGHTEN", 135, 64, BLUE)
    center_text(d, "WIND SPEEDS UP", 215, 72, CORAL)

    # shrinking gap between isobars
    gap = int(115 - 65*ease(t))
    cx = 555
    for i in range(6):
        x = cx - gap*2 + i*gap
        d.arc((x-320,430,x+320,1250),75,285,fill=BLUE,width=13)

    d.ellipse((465,690,645,870),outline=BLUE,width=16)
    d.text((525,715),"L",font=font(92,True),fill=BLUE)

    # moving wind streaks show speed increase
    sp = 260 + int(220*ease(t))
    for i,yy in enumerate((600,1040,1220)):
        x = int(100 + ((t*820 + i*230) % 740))
        arrow(d,x,yy,min(x+sp,980),yy-10,CORAL if i==1 else BLUE,19)

    owl_card(img,4,65,1160,w=350,h=295,angle=-4)

    if t < .5:
        caption_chip(d, "LOW PRESSURE DEEPENS", 1500, PALE_BLUE)
    else:
        caption_chip(d, "TIGHTER = FASTER", 1500, YELLOW)


def main():
    out = Path("output")
    out.mkdir(exist_ok=True)
    build = Path("build")
    build.mkdir(exist_ok=True)

    script = (
        "A nor'easter can hit the East Coast with wall-like winds. "
        "Cold Canadian air meets the warmer Atlantic. "
        "That contrast deepens low pressure. Tighter pressure lines mean faster wind."
    )
    narration = build / "prototype.wav"
    dur = generate_narration(script, narration, voice="af_sky", speed=1.0)

    if dur > 12.2:
        tempo = min(1.12, dur/11.7)
        sped = build / "prototype_sped.wav"
        subprocess.run(["ffmpeg","-y","-i",str(narration),"-filter:a",f"atempo={tempo:.4f}",str(sped)],check=True)
        narration = sped
        data, sr = sf.read(narration)
        dur = len(data)/sr

    total = max(11.4, min(dur+0.3, 12.0))
    frames = int(total*FPS)

    raw = build/"prototype_video.mp4"
    ff = subprocess.Popen([
        "ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}",
        "-r",str(FPS),"-i","-","-an","-c:v","libx264","-preset","veryfast",
        "-crf","19","-pix_fmt","yuv420p",str(raw)
    ],stdin=subprocess.PIPE)

    cuts = [0.0,0.24,0.46,0.68,1.0]
    for n in range(frames):
        p = (n/FPS)/total
        img = Image.new("RGBA",(W,H),BG+(255,))
        paper_texture(img)
        if p < cuts[1]:
            hook_scene(img,(p-cuts[0])/(cuts[1]-cuts[0]))
        elif p < cuts[2]:
            cold_scene(img,(p-cuts[1])/(cuts[2]-cuts[1]))
        elif p < cuts[3]:
            ocean_scene(img,(p-cuts[2])/(cuts[3]-cuts[2]))
        else:
            pressure_scene(img,(p-cuts[3])/(cuts[4]-cuts[3]))
        ff.stdin.write(img.convert("RGB").tobytes())

    ff.stdin.close()
    if ff.wait()!=0:
        raise SystemExit("video frame render failed")

    final = out/"paper_knowledge_prototype.mp4"
    subprocess.run([
        "ffmpeg","-y","-i",str(raw),"-i",str(narration),
        "-filter_complex","[1:a]loudnorm=I=-16:TP=-1.5:LRA=7[a]",
        "-map","0:v:0","-map","[a]","-c:v","copy","-c:a","aac","-b:a","160k",
        "-ar","48000","-shortest",str(final)
    ],check=True)

    print(final)


if __name__=="__main__":
    main()
