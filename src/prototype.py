from __future__ import annotations

import math
import subprocess
from pathlib import Path

import soundfile as sf
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

from tts import generate_narration

W, H = 1080, 1920
FPS = 30
BG = (245, 239, 224)
INK = (29, 33, 39)
BLUE = (54, 117, 214)
LIGHT_BLUE = (208, 228, 255)
CORAL = (232, 104, 85)
LIGHT_CORAL = (255, 223, 215)
YELLOW = (245, 195, 71)
WHITE = (255, 255, 255)


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def text_center(draw, text, y, size, fill=INK, bold=True):
    f = font(size, bold)
    box = draw.textbbox((0, 0), text, font=f)
    x = (W - (box[2] - box[0])) // 2
    draw.text((x, y), text, font=f, fill=fill)


def rounded_label(draw, x, y, text, bg, fg=INK, size=42):
    f = font(size, True)
    box = draw.textbbox((0, 0), text, font=f)
    tw = box[2] - box[0]
    th = box[3] - box[1]
    pad_x, pad_y = 28, 17
    draw.rounded_rectangle((x, y, x + tw + pad_x * 2, y + th + pad_y * 2), 28, fill=bg)
    draw.text((x + pad_x, y + pad_y - 3), text, font=f, fill=fg)


def arrow(draw, x1, y1, x2, y2, fill, width=18):
    draw.line((x1, y1, x2, y2), fill=fill, width=width)
    ang = math.atan2(y2-y1, x2-x1)
    L = 34
    for d in (2.6, -2.6):
        draw.line((x2, y2, x2 + L*math.cos(ang+d), y2 + L*math.sin(ang+d)), fill=fill, width=width)


def paper_texture(img: Image.Image):
    d = ImageDraw.Draw(img)
    for y in range(0, H, 34):
        alpha = 8 + ((y // 34) % 3) * 3
        d.line((0, y, W, y), fill=(120, 110, 90, alpha), width=1)


def load_owl(i=0, max_size=(410, 410)):
    poses = sorted(Path("assets/mascot").glob("pose*.png"))
    if not poses:
        return None
    owl = Image.open(poses[i % len(poses)]).convert("RGBA")
    owl.thumbnail(max_size, Image.Resampling.LANCZOS)
    return owl


def put_owl(img, idx, x, y, scale=1.0):
    owl = load_owl(idx, (int(410*scale), int(410*scale)))
    if owl is None:
        return
    shadow = Image.new("RGBA", img.size, (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((x+30, y+owl.height-45, x+owl.width-25, y+owl.height+12), fill=(0,0,0,35))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    img.alpha_composite(shadow)
    img.alpha_composite(owl, (x, y))


def coast_shape(draw, offset=0):
    pts = [
        (780+offset, 330),(735+offset, 450),(770+offset, 560),(715+offset, 680),
        (750+offset, 810),(700+offset, 930),(735+offset, 1050),(695+offset, 1200),
        (740+offset, 1360),(700+offset, 1510),(760+offset, 1680)
    ]
    draw.line(pts, fill=INK, width=18)
    draw.text((785+offset, 340), "EAST COAST", font=font(38, True), fill=INK)


def caption(draw, top, words):
    # words = [(text, active)]
    x = 75
    y = top
    for text, active in words:
        f = font(48, True)
        box = draw.textbbox((0,0), text, font=f)
        tw = box[2]-box[0]
        if x + tw > W-75:
            x = 75
            y += 70
        if active:
            draw.rounded_rectangle((x-8,y-6,x+tw+8,y+56), 15, fill=YELLOW)
        draw.text((x,y), text, font=f, fill=INK)
        x += tw + 18


def scene1(img, t):
    d = ImageDraw.Draw(img)
    d.text((55,45), "PAPER KNOWLEDGE", font=font(36, True), fill=(90,92,95))
    text_center(d, "A NOR'EASTER CAN TURN", 155, 58)
    text_center(d, "THE COAST INTO A WIND TUNNEL.", 225, 58, BLUE)

    coast_shape(d)
    # moving wind bands
    for j in range(4):
        phase = (t*180 + j*180) % 900
        y = 520 + j*200
        x1 = -180 + phase
        x2 = x1 + 330
        d.arc((x1, y-70, x2, y+100), 190, 350, fill=BLUE, width=22)

    # bent tree = immediate visual consequence
    d.line((900,1250,850,1580), fill=(95,75,55), width=28)
    for yy in (1310,1390,1470):
        d.line((880,yy,790,yy-65), fill=(82,122,67), width=24)

    put_owl(img, 0, 70, 1210, 1.0)

    if t < .42:
        caption(d, 1660, [("A",False),("nor'easter",True),("can",False),("hit",False),("the",False),("East",False),("Coast",False)])
    else:
        caption(d, 1660, [("with",False),("wall-like",True),("winds.",False)])


def scene2(img, t):
    d = ImageDraw.Draw(img)
    d.text((55,45), "PAPER KNOWLEDGE", font=font(36, True), fill=(90,92,95))
    text_center(d, "THE COLLISION", 150, 68, BLUE)

    # cold / warm paper panels slide toward each other
    k = ease(t)
    left_x = int(-220 + 260*k)
    right_x = int(900 - 260*k)
    d.rounded_rectangle((left_x,420,left_x+470,1180), 55, fill=LIGHT_BLUE)
    d.rounded_rectangle((right_x,420,right_x+470,1180), 55, fill=LIGHT_CORAL)
    d.text((left_x+90,520), "COLD", font=font(74,True), fill=BLUE)
    d.text((left_x+65,615), "CANADIAN", font=font(48,True), fill=BLUE)
    d.text((left_x+120,680), "AIR", font=font(62,True), fill=BLUE)
    d.text((right_x+95,520), "WARMER", font=font(58,True), fill=CORAL)
    d.text((right_x+80,600), "ATLANTIC", font=font(52,True), fill=CORAL)
    d.text((right_x+130,670), "AIR", font=font(62,True), fill=CORAL)

    # collision pulse
    r = 45 + 90*abs(math.sin(t*math.pi))
    d.ellipse((W//2-r,800-r,W//2+r,800+r), outline=YELLOW, width=18)
    arrow(d, 300, 930, 490, 930, BLUE, 20)
    arrow(d, 780, 930, 590, 930, CORAL, 20)

    put_owl(img, 2, 585, 1180, .92)
    caption(d, 1640, [("Cold",True),("Canadian",False),("air",False),("meets",False),("the",False),("warmer",True),("Atlantic.",False)])


def scene3(img, t):
    d = ImageDraw.Draw(img)
    d.text((55,45), "PAPER KNOWLEDGE", font=font(36, True), fill=(90,92,95))
    text_center(d, "TIGHTER PRESSURE LINES", 145, 60, BLUE)
    text_center(d, "= FASTER WIND", 220, 72, CORAL)

    # isobars compress through time
    gap = int(110 - 58*ease(t))
    start = W//2 - gap*2
    for i in range(5):
        x = start + i*gap
        d.arc((x-310,480,x+310,1210), 80, 280, fill=BLUE, width=12)

    # low center + fast wind arrows
    d.ellipse((430,680,650,900), outline=BLUE, width=18)
    d.text((500,715), "L", font=font(110,True), fill=BLUE)
    speed = ease(t)
    for j,y in enumerate((540,1050,1240)):
        x = int(120 + ((t*650 + j*220) % 700))
        arrow(d, x, y, min(x+220+int(100*speed), 960), y-20, CORAL if j==1 else BLUE, 18)

    put_owl(img, 4, 70, 1190, .98)
    if t < .48:
        caption(d, 1640, [("That",False),("contrast",True),("deepens",False),("low",False),("pressure.",False)])
    else:
        caption(d, 1640, [("Tighter",True),("pressure",False),("lines",False),("mean",False),("faster",True),("wind.",False)])


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

    # keep preview in a true short-form window; if TTS runs long, lightly speed audio, never slow it
    target = 14.5
    if dur > 15.5:
        tempo = min(1.18, dur / target)
        sped = build / "prototype_sped.wav"
        subprocess.run([
            "ffmpeg","-y","-i",str(narration),"-filter:a",f"atempo={tempo:.4f}",str(sped)
        ], check=True)
        narration = sped
        data, sr = sf.read(narration)
        dur = len(data) / sr

    total = min(max(dur, 12.0), 15.5)
    frame_count = int(total * FPS)

    video_no_audio = build / "prototype_video.mp4"
    ff = subprocess.Popen([
        "ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}",
        "-r",str(FPS),"-i","-",
        "-an","-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p",
        str(video_no_audio)
    ], stdin=subprocess.PIPE)

    for n in range(frame_count):
        sec = n / FPS
        img = Image.new("RGBA",(W,H),BG+(255,))
        paper_texture(img)
        if sec < total*0.30:
            scene1(img, sec/(total*0.30))
        elif sec < total*0.64:
            scene2(img, (sec-total*0.30)/(total*0.34))
        else:
            scene3(img, (sec-total*0.64)/(total*0.36))
        ff.stdin.write(img.convert("RGB").tobytes())

    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("video frame render failed")

    final = out / "paper_knowledge_prototype.mp4"
    subprocess.run([
        "ffmpeg","-y","-i",str(video_no_audio),"-i",str(narration),
        "-filter_complex","[1:a]loudnorm=I=-16:TP=-1.5:LRA=7[a]",
        "-map","0:v:0","-map","[a]","-c:v","copy","-c:a","aac","-b:a","160k",
        "-shortest",str(final)
    ], check=True)

    print(final)


if __name__ == "__main__":
    main()
