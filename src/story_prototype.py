from __future__ import annotations

import math
import subprocess
from pathlib import Path

import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

from tts import generate_narration

W,H,FPS = 1080,1920,30
BG=(242,236,221)
INK=(26,31,38)
BLUE=(53,119,222)
BLUE2=(155,202,255)
ORANGE=(242,132,82)
LAND=(214,202,174)
SEA=(186,218,238)
WHITE=(255,255,255)
YELLOW=(249,205,76)


def font(size,bold=False):
    ps=[
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in ps:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()


def clamp(x): return max(0,min(1,x))
def ease(x):
    x=clamp(x)
    return 1-(1-x)**3


def paper(img):
    d=ImageDraw.Draw(img)
    for y in range(0,H,28):
        d.line((0,y,W,y),fill=(112,100,80,12),width=1)


def arrow(d,a,b,color,width=18):
    d.line((a,b),fill=color,width=width)
    x1,y1=a; x2,y2=b
    ang=math.atan2(y2-y1,x2-x1)
    L=30
    for q in (2.55,-2.55):
        d.line((x2,y2,x2+L*math.cos(ang+q),y2+L*math.sin(ang+q)),fill=color,width=width)


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


def coast_points():
    return [(690,120),(650,250),(700,380),(645,515),(690,660),(650,810),(710,950),(660,1110),(715,1260),(675,1420),(730,1580),(700,1810)]


def draw_coast_world(d,wind=0.0,storm=0.0):
    # ocean / land split
    pts=coast_points()
    land=[(x,y) for x,y in pts]+[(W,1810),(W,120)]
    d.polygon(land,fill=LAND)
    d.rectangle((0,0,640,H),fill=SEA)
    d.line(pts,fill=INK,width=15)

    # ocean waves
    for row in range(5):
        yy=350+row*250
        phase=int(wind*80+row*50)
        for xx in range(-100+phase,650,160):
            d.arc((xx,yy,xx+150,yy+70),180,360,fill=(88,153,191),width=9)

    # house near coast
    hx,hy=730,1180
    d.rectangle((hx,hy,hx+220,hy+190),fill=(239,224,186),outline=INK,width=10)
    d.polygon([(hx-25,hy),(hx+110,hy-120),(hx+245,hy)],fill=(154,85,69),outline=INK)
    d.rectangle((hx+82,hy+95,hx+140,hy+190),fill=(112,83,60))

    # tree bends with wind
    bend=int(95*wind)
    tx,ty=870,990
    d.line((tx,ty+250,tx-bend,ty),fill=(102,75,49),width=25)
    cx,cy=tx-bend,ty
    for dx,dy in [(-70,-20),(-30,-65),(20,-45),(55,-5),(-15,15)]:
        d.ellipse((cx+dx-45,cy+dy-35,cx+dx+45,cy+dy+35),fill=(71,121,69))

    # rain / gust streaks
    n=int(5+storm*12)
    for i in range(n):
        y=240+i*85
        x=int(30+((i*137+wind*500)%700))
        d.line((x,y,x+180+int(120*wind),y-25),fill=(255,255,255,155),width=8)


def draw_map(d,cold=0,warm=0,low=0,isobars=0,ne=0):
    # base map
    d.rectangle((0,0,W,H),fill=BG)
    d.rectangle((0,0,620,H),fill=(216,231,241))
    pts=[(650,130),(620,280),(660,430),(610,590),(650,760),(615,940),(665,1110),(620,1290),(665,1480),(635,1800)]
    land=pts+[(W,1800),(W,130)]
    d.polygon(land,fill=LAND)
    d.line(pts,fill=INK,width=14)

    # cold Canadian flow
    if cold>0:
        k=ease(cold)
        for i in range(3):
            x=220+i*135
            y1=int(-160+850*k+i*45)
            arrow(d,(x,y1),(x+35,y1+330),BLUE,22)

    # warmer Atlantic flow
    if warm>0:
        k=ease(warm)
        for i in range(3):
            x=180+i*150
            y=1250+i*55
            start=(x-420+int(500*k),y)
            end=(x+int(170*k),y-250)
            arrow(d,start,end,ORANGE,22)

    # low grows
    if low>0:
        k=ease(low)
        r=int(35+90*k)
        cx,cy=560,900
        d.ellipse((cx-r,cy-r,cx+r,cy+r),outline=BLUE,width=17)
        f=font(int(42+80*k),True)
        d.text((cx-int(20+28*k),cy-int(30+48*k)),"L",font=f,fill=BLUE)

    # isobars draw and tighten
    if isobars>0:
        k=ease(isobars)
        cx,cy=560,900
        for j in range(4):
            rr=int((150+j*85)*(1-0.16*k))
            d.arc((cx-rr,cy-rr,cx+rr,cy+rr),5,355,fill=BLUE,width=10)

    if ne>0:
        k=ease(ne)
        for j in range(4):
            y=520+j*210
            x1=int(80+260*(1-k))
            x2=int(540+160*k)
            arrow(d,(x1,y),(x2,y+100),ORANGE if j==1 else BLUE,20)


def render_frame(sec,total):
    img=Image.new("RGBA",(W,H),BG+(255,))
    paper(img)
    d=ImageDraw.Draw(img)

    # 8 meaningful beats across ~10s
    b=[0,1.25,2.5,3.7,4.9,6.1,7.3,8.6,total]

    if sec<b[1]:
        t=(sec-b[0])/(b[1]-b[0])
        draw_coast_world(d,wind=.35+.55*t,storm=.35+.5*t)
        if sec<.55: text_center(d,"WHY SO WINDY?",170,78)
        subtitle(d,"A nor'easter hits hard")
    elif sec<b[2]:
        t=(sec-b[1])/(b[2]-b[1])
        draw_map(d,cold=t)
        subtitle(d,"Cold air drops south")
    elif sec<b[3]:
        t=(sec-b[2])/(b[3]-b[2])
        draw_map(d,cold=1,warm=t)
        subtitle(d,"Milder Atlantic air pushes in")
    elif sec<b[4]:
        t=(sec-b[3])/(b[4]-b[3])
        draw_map(d,cold=1,warm=1,low=t)
        subtitle(d,"Low pressure deepens")
    elif sec<b[5]:
        t=(sec-b[4])/(b[5]-b[4])
        draw_map(d,cold=1,warm=1,low=1,isobars=t)
        subtitle(d,"Pressure lines tighten")
    elif sec<b[6]:
        t=(sec-b[5])/(b[6]-b[5])
        draw_map(d,cold=1,warm=1,low=1,isobars=1,ne=t)
        subtitle(d,"Air speeds up")
    elif sec<b[7]:
        t=(sec-b[6])/(b[7]-b[6])
        draw_map(d,cold=1,warm=1,low=1,isobars=1,ne=1)
        # camera-style emphasis by drawing a pulse around coast
        rr=int(80+80*abs(math.sin(t*math.pi)))
        d.ellipse((600-rr,970-rr,600+rr,970+rr),outline=YELLOW,width=18)
        subtitle(d,"Northeast wind hits the coast")
    else:
        t=(sec-b[7])/(b[8]-b[7])
        draw_coast_world(d,wind=.9,storm=.9)
        text_center(d,"PRESSURE DIFFERENCE",220,55)
        text_center(d,"→ WIND",300,78,fill=YELLOW)
        subtitle(d,"That's the pressure gradient")

    return img


def main():
    out=Path("output"); out.mkdir(exist_ok=True)
    build=Path("build"); build.mkdir(exist_ok=True)

    script=(
        "Why can a nor'easter hit the coast so hard? "
        "Cold Canadian air meets the milder Atlantic. "
        "That deepens low pressure, tightens the pressure gradient, and speeds the wind up."
    )
    narr=build/"story.wav"
    dur=generate_narration(script,narr,voice="af_sky",speed=1.03)

    # Never slow the narration; lightly speed only if needed.
    if dur>10.8:
        tempo=min(1.12,dur/10.4)
        fast=build/"story_fast.wav"
        subprocess.run(["ffmpeg","-y","-i",str(narr),"-filter:a",f"atempo={tempo:.4f}",str(fast)],check=True)
        narr=fast
        data,sr=sf.read(narr); dur=len(data)/sr

    total=max(9.8,min(dur+.15,10.8))
    raw=build/"story_raw.mp4"
    proc=subprocess.Popen([
        "ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}",
        "-r",str(FPS),"-i","-","-an","-c:v","libx264","-preset","veryfast",
        "-crf","19","-pix_fmt","yuv420p",str(raw)
    ],stdin=subprocess.PIPE)

    frames=int(total*FPS)
    for n in range(frames):
        img=render_frame(n/FPS,total)
        proc.stdin.write(img.convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait()!=0: raise SystemExit("render failed")

    # synthesize a very subtle wind bed; fully original, no copyrighted music.
    final=out/"paper_knowledge_story_prototype.mp4"
    subprocess.run([
        "ffmpeg","-y",
        "-i",str(raw),"-i",str(narr),
        "-f","lavfi","-t",f"{total:.3f}","-i","anoisesrc=color=pink:amplitude=0.018:sample_rate=48000",
        "-filter_complex",
        "[1:a]loudnorm=I=-16:TP=-1.5:LRA=7[n];"
        "[2:a]highpass=f=180,lowpass=f=1600,volume=0.23[w];"
        "[n][w]amix=inputs=2:duration=first:dropout_transition=0[a]",
        "-map","0:v:0","-map","[a]","-c:v","copy","-c:a","aac","-b:a","160k",
        "-ar","48000","-shortest",str(final)
    ],check=True)
    print(final)


if __name__=="__main__":
    main()
