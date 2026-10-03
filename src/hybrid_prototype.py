from __future__ import annotations

import io
import math
import subprocess
import urllib.request
from pathlib import Path

import soundfile as sf
from PIL import Image, ImageDraw, ImageFont, ImageSequence, ImageOps, ImageFilter

from tts import generate_narration

W,H,FPS=1080,1920,30
INK=(26,31,38)
BLUE=(52,118,222)
ORANGE=(242,128,78)
YELLOW=(248,204,74)
WHITE=(255,255,255)
BG=(242,236,221)

GIF_URL="https://www.nesdis.noaa.gov/s3/2025-08/noreasterBW.gif"
THERMAL_URL="https://www.nesdis.noaa.gov/s3/styles/webp/s3/2025-08/noreasterVIIRS.png.webp?itok=wCuFFTtW"
FORMATION_URL="https://www.nesdis.noaa.gov/s3/styles/webp/s3/2025-08/noreasterformation.jpg.webp?itok=Du5nao6i"


def font(size,bold=False):
    paths=[
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p,size)
    return ImageFont.load_default()


def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 PaperKnowledge/1.0"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read()


def fit_vertical(im):
    im=im.convert("RGB")
    # Fill 9:16 while preserving center; satellite imagery benefits from a tight crop.
    return ImageOps.fit(im,(W,H),method=Image.Resampling.LANCZOS,centering=(0.48,0.50))


def text_center(d,text,y,size,fill=WHITE,stroke=5):
    f=font(size,True)
    b=d.textbbox((0,0),text,font=f,stroke_width=stroke)
    x=(W-(b[2]-b[0]))//2
    d.text((x,y),text,font=f,fill=fill,stroke_width=stroke,stroke_fill=(0,0,0,190))


def subtitle(d,text,y=1645):
    f=font(54,True)
    b=d.textbbox((0,0),text,font=f,stroke_width=5)
    x=(W-(b[2]-b[0]))//2
    d.text((x,y),text,font=f,fill=WHITE,stroke_width=5,stroke_fill=INK)


def credit(d):
    d.text((30,1855),"Satellite imagery: NOAA",font=font(25,True),fill=(255,255,255,220),stroke_width=3,stroke_fill=(0,0,0,150))


def arrow(d,x1,y1,x2,y2,color,width=18):
    d.line((x1,y1,x2,y2),fill=color,width=width)
    a=math.atan2(y2-y1,x2-x1)
    L=30
    for q in (2.55,-2.55):
        d.line((x2,y2,x2+L*math.cos(a+q),y2+L*math.sin(a+q)),fill=color,width=width)


def zoom_crop(im,scale,center=(.5,.5)):
    nw=int(W*scale); nh=int(H*scale)
    z=im.resize((nw,nh),Image.Resampling.LANCZOS)
    cx=int(center[0]*nw); cy=int(center[1]*nh)
    left=max(0,min(nw-W,cx-W//2))
    top=max(0,min(nh-H,cy-H//2))
    return z.crop((left,top,left+W,top+H))


def diagram_frame(t):
    img=Image.new("RGB",(W,H),BG)
    d=ImageDraw.Draw(img)

    # Coast as geography, not slide furniture
    sea=(203,225,241); land=(216,204,178)
    d.rectangle((0,0,620,H),fill=sea)
    pts=[(660,120),(625,280),(670,430),(620,610),(665,790),(620,970),(675,1140),(630,1320),(680,1510),(645,1810)]
    d.polygon(pts+[(W,1810),(W,120)],fill=land)
    d.line(pts,fill=INK,width=14)

    # Cold air from Canada drops south
    k=min(1,t*2)
    for i in range(3):
        x=210+i*150
        yy=-180+int(820*k)+i*35
        arrow(d,x,yy,x+35,yy+330,BLUE,22)

    # Warm Atlantic inflow appears second
    if t>.3:
        q=min(1,(t-.3)/.45)
        for i in range(3):
            y=1150+i*75
            arrow(d,-80+int(450*q)+i*50,y,520,y-260,ORANGE,22)

    # Low pressure grows at meeting point
    if t>.58:
        q=min(1,(t-.58)/.42)
        r=int(40+95*q)
        cx,cy=560,900
        d.ellipse((cx-r,cy-r,cx+r,cy+r),outline=BLUE,width=16)
        d.text((cx-37,cy-60),"L",font=font(100,True),fill=BLUE)

    subtitle(d,"Cold air meets the milder Atlantic")
    return img


def main():
    out=Path("output"); out.mkdir(exist_ok=True)
    build=Path("build"); build.mkdir(exist_ok=True)

    gif_data=get(GIF_URL)
    thermal_data=get(THERMAL_URL)
    formation_data=get(FORMATION_URL)

    gif=Image.open(io.BytesIO(gif_data))
    gif_frames=[fit_vertical(f.copy()) for f in ImageSequence.Iterator(gif)]
    thermal=fit_vertical(Image.open(io.BytesIO(thermal_data)))
    formation=fit_vertical(Image.open(io.BytesIO(formation_data)))

    script=(
        "This is a nor'easter from space. "
        "Cold Canadian air meets the milder Atlantic. "
        "That deepens low pressure, tightens the pressure gradient, "
        "and drives strong northeast winds into the coast."
    )
    narr=build/"hybrid.wav"
    dur=generate_narration(script,narr,voice="af_sky",speed=1.03)

    # Keep natural delivery; only a light speed-up if needed.
    if dur>10.8:
        tempo=min(1.12,dur/10.4)
        fast=build/"hybrid_fast.wav"
        subprocess.run(["ffmpeg","-y","-i",str(narr),"-filter:a",f"atempo={tempo:.4f}",str(fast)],check=True)
        narr=fast
        data,sr=sf.read(narr); dur=len(data)/sr

    # Match the visual timeline to the actual narration so no beats are truncated.
    data,sr=sf.read(narr)
    dur=len(data)/sr
    if dur>8.4:
        tempo=min(1.14,dur/7.9)
        fast2=build/"hybrid_fast2.wav"
        subprocess.run(["ffmpeg","-y","-i",str(narr),"-filter:a",f"atempo={tempo:.4f}",str(fast2)],check=True)
        narr=fast2
        data,sr=sf.read(narr)
        dur=len(data)/sr

    total=dur
    frames=int(total*FPS)

    raw=build/"hybrid_raw.mp4"
    ff=subprocess.Popen([
        "ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}",
        "-r",str(FPS),"-i","-","-an","-c:v","libx264","-preset","veryfast",
        "-crf","19","-pix_fmt","yuv420p",str(raw)
    ],stdin=subprocess.PIPE)

    for n in range(frames):
        sec=n/FPS
        p=sec/total

        # 7 visually distinct beats across the actual narration (~1 second each).
        if p<.14:
            q=p/.14
            idx=int(q*max(1,len(gif_frames)-1))
            img=gif_frames[min(idx,len(gif_frames)-1)].copy()
            img=zoom_crop(img,1.04+0.07*q,(.49,.49))
            d=ImageDraw.Draw(img)
            text_center(d,"NOR'EASTER",145,78)
            subtitle(d,"FROM SPACE")
            credit(d)

        elif p<.28:
            q=(p-.14)/.14
            img=zoom_crop(thermal,1.02+0.20*q,(.48,.53))
            d=ImageDraw.Draw(img)
            pulse=70+42*abs(math.sin(q*math.pi))
            d.ellipse((475-pulse,980-pulse,475+pulse,980+pulse),outline=YELLOW,width=18)
            d.text((505,928),"LOW",font=font(56,True),fill=YELLOW,stroke_width=4,stroke_fill=INK)
            subtitle(d,"LOW PRESSURE")
            credit(d)

        elif p<.42:
            q=(p-.28)/.14
            img=zoom_crop(formation,1.03+0.17*q,(.40,.57))
            d=ImageDraw.Draw(img)
            subtitle(d,"COLD AIR SOUTH")
            d.text((30,1855),"Graphic: NOAA/JPL-Caltech",font=font(25,True),fill=(255,255,255,220),stroke_width=3,stroke_fill=(0,0,0,150))

        elif p<.56:
            q=(p-.42)/.14
            img=zoom_crop(formation,1.16+0.17*q,(.47,.60))
            d=ImageDraw.Draw(img)
            subtitle(d,"JET STREAM")
            d.text((30,1855),"Graphic: NOAA/JPL-Caltech",font=font(25,True),fill=(255,255,255,220),stroke_width=3,stroke_fill=(0,0,0,150))

        elif p<.70:
            q=(p-.56)/.14
            img=zoom_crop(formation,1.22+0.16*q,(.64,.54))
            d=ImageDraw.Draw(img)
            subtitle(d,"NORTHEAST WINDS")
            d.text((30,1855),"Graphic: NOAA/JPL-Caltech",font=font(25,True),fill=(255,255,255,220),stroke_width=3,stroke_fill=(0,0,0,150))

        elif p<.84:
            q=(p-.70)/.14
            img=zoom_crop(thermal,1.10+0.18*q,(.44,.56))
            d=ImageDraw.Draw(img)
            for j in range(3):
                y=720+j*170
                x1=70+int(90*q)
                x2=650+int(160*q)
                arrow(d,x1,y,x2,y+70,BLUE if j!=1 else ORANGE,18)
            subtitle(d,"TIGHTER GRADIENT")
            credit(d)

        else:
            q=(p-.84)/.16
            idx=int((.55+.45*q)*max(1,len(gif_frames)-1))
            img=gif_frames[min(idx,len(gif_frames)-1)].copy()
            img=zoom_crop(img,1.08+0.10*q,(.52,.50))
            d=ImageDraw.Draw(img)
            text_center(d,"FASTER WIND",220,64,fill=YELLOW)
            subtitle(d,"HITS THE COAST")
            credit(d)

        ff.stdin.write(img.convert("RGB").tobytes())

    ff.stdin.close()
    if ff.wait()!=0:
        raise SystemExit("video render failed")

    final=out/"paper_knowledge_hybrid_prototype.mp4"
    subprocess.run([
        "ffmpeg","-y",
        "-i",str(raw),"-i",str(narr),
        "-f","lavfi","-t",f"{total:.3f}","-i","anoisesrc=color=pink:amplitude=0.012:sample_rate=48000",
        "-filter_complex",
        "[1:a]loudnorm=I=-16:TP=-1.5:LRA=7[n];"
        "[2:a]highpass=f=180,lowpass=f=1500,volume=0.12[w];"
        "[n][w]amix=inputs=2:duration=first:dropout_transition=0[a]",
        "-map","0:v:0","-map","[a]","-c:v","copy","-c:a","aac","-b:a","160k",
        "-ar","48000","-t",f"{total:.3f}",str(final)
    ],check=True)

    print(final)


if __name__=="__main__":
    main()
