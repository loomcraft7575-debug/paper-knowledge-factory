from __future__ import annotations

import io
import json
import math
import subprocess
import urllib.request
from collections import deque
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageSequence

from tts import generate_narration

W,H,FPS=1080,1920,30
INK=(25,30,38)
BLUE=(52,118,222)
ORANGE=(244,127,75)
YELLOW=(249,204,72)
WHITE=(255,255,255)
BG=(242,236,221)

URLS={
    "gif2018":"https://www.nesdis.noaa.gov/s3/2025-08/noreasterBW.gif",
    "thermal":"https://www.nesdis.noaa.gov/s3/styles/webp/s3/2025-08/noreasterVIIRS.png.webp?itok=wCuFFTtW",
    "formation":"https://www.nesdis.noaa.gov/s3/styles/webp/s3/2025-08/noreasterformation.jpg.webp?itok=Du5nao6i",
    "geo2018a":"https://www.nesdis.noaa.gov/s3/migrated/20180302-noreaster.png",
    "geo2018b":"https://www.nesdis.noaa.gov/s3/migrated/20180302-noreaster.png",
    "geo2018c":"https://www.nesdis.noaa.gov/s3/migrated/20180322-noreaster.png",
    "gif2020":"https://www.nesdis.noaa.gov/s3/migrated/20201217_noreaster-mp4.gif",
}

SCRIPT="""Why can a nor'easter feel like a wall of wind? From space, the storm looks like a giant comma spinning beside the East Coast. The engine starts when cold Canadian air dives south and meets much milder air over the Atlantic, warmed by the Gulf Stream. That sharp temperature contrast helps a low-pressure system deepen offshore. Air then rushes toward the low. But Earth is rotating, so the flow bends and spirals counterclockwise around the storm. Now look at the pressure lines around the center. When those lines are packed tightly together, pressure changes fast over a short distance. That's a strong pressure gradient — and a strong pressure gradient means stronger wind. Ahead of the storm, that circulation often pushes air toward the coast from the northeast, which is where the name nor'easter comes from. The same storm can also pull in Atlantic moisture, producing heavy snow, rain, coastal flooding, and huge waves. So the wind isn't a separate feature. It's the atmosphere trying to balance a big pressure difference — while the spinning storm steers that wind straight at the coast."""


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
    with urllib.request.urlopen(req,timeout=35) as r:
        return r.read()


def load_image(url):
    return Image.open(io.BytesIO(get(url))).convert("RGB")


def load_gif(url):
    im=Image.open(io.BytesIO(get(url)))
    return [f.convert("RGB") for f in ImageSequence.Iterator(im)]


def fit_vertical(im, center=(.5,.5)):
    return ImageOps.fit(im.convert("RGB"),(W,H),method=Image.Resampling.LANCZOS,centering=center)


def zoom_crop(im,scale,center=(.5,.5)):
    base=fit_vertical(im,center)
    nw=int(W*scale); nh=int(H*scale)
    z=base.resize((nw,nh),Image.Resampling.LANCZOS)
    cx=int(center[0]*nw); cy=int(center[1]*nh)
    left=max(0,min(nw-W,cx-W//2))
    top=max(0,min(nh-H,cy-H//2))
    return z.crop((left,top,left+W,top+H))


def text_center(d,text,y,size,fill=WHITE,stroke=5):
    f=font(size,True)
    b=d.textbbox((0,0),text,font=f,stroke_width=stroke)
    d.text(((W-(b[2]-b[0]))//2,y),text,font=f,fill=fill,stroke_width=stroke,stroke_fill=INK)


def subtitle(d,text,y=1585,size=48,max_width=910):
    display=text.strip()
    if display.isupper():
        display=display.capitalize()
    f=font(size,True)
    words=display.split()
    lines=[]
    current=""
    for word in words:
        trial=(current+" "+word).strip()
        box=d.textbbox((0,0),trial,font=f,stroke_width=5)
        if current and (box[2]-box[0])>max_width:
            lines.append(current)
            current=word
        else:
            current=trial
    if current:
        lines.append(current)
    if len(lines)>2:
        lines=[" ".join(lines[:-1]),lines[-1]]
    line_h=size+16
    start_y=y-(len(lines)-1)*(line_h//2)
    for i,line in enumerate(lines):
        b=d.textbbox((0,0),line,font=f,stroke_width=5)
        x=(W-(b[2]-b[0]))//2
        d.text((x,start_y+i*line_h),line,font=f,fill=WHITE,stroke_width=5,stroke_fill=INK)


def credit(d,text="NOAA satellite imagery"):
    d.text((28,1860),text,font=font(24,True),fill=(255,255,255),stroke_width=3,stroke_fill=(0,0,0))


def arrow(d,x1,y1,x2,y2,color=BLUE,width=18):
    d.line((x1,y1,x2,y2),fill=color,width=width)
    a=math.atan2(y2-y1,x2-x1)
    L=30
    for q in (2.55,-2.55):
        d.line((x2,y2,x2+L*math.cos(a+q),y2+L*math.sin(a+q)),fill=color,width=width)


def curved_arrow(d, box, start, end, color=BLUE, width=16):
    d.arc(box,start,end,fill=color,width=width)
    # simple arrow head near arc end
    x1,y1,x2,y2=box
    cx=(x1+x2)/2; cy=(y1+y2)/2
    rx=(x2-x1)/2; ry=(y2-y1)/2
    ang=math.radians(end)
    ex=cx+rx*math.cos(ang); ey=cy+ry*math.sin(ang)
    tang=ang+math.pi/2
    L=28
    for off in (2.55,-2.55):
        d.line((ex,ey,ex+L*math.cos(tang+off),ey+L*math.sin(tang+off)),fill=color,width=width)


def flood_transparency(crop):
    arr=np.array(crop.convert("RGBA"))
    rgb=arr[:,:,:3].astype(np.int16)
    h,w=rgb.shape[:2]
    # Background is light warm gray; only flood through near-background pixels connected to an edge.
    corners=np.vstack([rgb[:15,:15].reshape(-1,3),rgb[:15,-15:].reshape(-1,3),rgb[-15:,:15].reshape(-1,3),rgb[-15:,-15:].reshape(-1,3)])
    bg=np.median(corners,axis=0)
    dist=np.sqrt(((rgb-bg)**2).sum(axis=2))
    candidate=dist<42

    seen=np.zeros((h,w),dtype=bool)
    q=deque()
    for x in range(w):
        if candidate[0,x]: q.append((0,x)); seen[0,x]=True
        if candidate[h-1,x] and not seen[h-1,x]: q.append((h-1,x)); seen[h-1,x]=True
    for y in range(h):
        if candidate[y,0] and not seen[y,0]: q.append((y,0)); seen[y,0]=True
        if candidate[y,w-1] and not seen[y,w-1]: q.append((y,w-1)); seen[y,w-1]=True
    while q:
        y,x=q.popleft()
        for yy,xx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
            if 0<=yy<h and 0<=xx<w and candidate[yy,xx] and not seen[yy,xx]:
                seen[yy,xx]=True
                q.append((yy,xx))

    alpha=np.where(seen,0,255).astype(np.uint8)
    # soften only the very outer edge
    alpha=Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(1.1))
    out=Image.fromarray(arr)
    out.putalpha(alpha)
    bbox=out.getchannel("A").getbbox()
    return out.crop(bbox) if bbox else out


def load_owl_sprites():
    sheet=Image.open("assets/mascot/action-poses.png").convert("RGB")
    sw,sh=sheet.size
    cw=sw//3
    # crop above labels
    y0a,y1a=0,int(sh*.43)
    y0b,y1b=int(sh*.48),int(sh*.91)
    sprites=[]
    for row,(ya,yb) in enumerate(((y0a,y1a),(y0b,y1b))):
        for col in range(3):
            x0=col*cw; x1=(col+1)*cw
            sprites.append(flood_transparency(sheet.crop((x0,ya,x1,yb))))
    return sprites


def place_owl(img,sprites,idx,x,y,height=430,flip=False,bob=0):
    sp=sprites[idx%len(sprites)].copy()
    scale=height/sp.height
    sp=sp.resize((max(1,int(sp.width*scale)),height),Image.Resampling.LANCZOS)
    if flip:
        sp=sp.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    y=int(y+bob)
    # soft shadow
    a=sp.getchannel("A")
    shadow=Image.new("RGBA",sp.size,(0,0,0,60)); shadow.putalpha(a.filter(ImageFilter.GaussianBlur(12)))
    img=img.convert("RGBA")
    img.alpha_composite(shadow,(x+14,y+18))
    img.alpha_composite(sp,(x,y))
    return img.convert("RGB")


def graphic_card(background,source,mode="full",progress=0):
    bg=fit_vertical(background).filter(ImageFilter.GaussianBlur(20)).convert("RGBA")
    bg.alpha_composite(Image.new("RGBA",(W,H),(0,0,0,70)))
    src=source.convert("RGB")
    if mode=="full":
        card=ImageOps.contain(src,(950,760),method=Image.Resampling.LANCZOS)
    elif mode=="jet":
        crop=src.crop((0,int(src.height*.15),int(src.width*.74),src.height))
        card=ImageOps.fit(crop,(930,800),method=Image.Resampling.LANCZOS,centering=(.5,.57))
    else:
        crop=src.crop((int(src.width*.36),int(src.height*.24),src.width,int(src.height*.92)))
        card=ImageOps.fit(crop,(930,800),method=Image.Resampling.LANCZOS,centering=(.58,.5))
    scale=1.0+.035*progress
    card=card.resize((int(card.width*scale),int(card.height*scale)),Image.Resampling.LANCZOS)
    x=(W-card.width)//2; y=445
    layer=Image.new("RGBA",(W,H),(0,0,0,0))
    shadow=Image.new("RGBA",(card.width+40,card.height+40),(0,0,0,0))
    sd=ImageDraw.Draw(shadow); sd.rounded_rectangle((18,18,card.width+22,card.height+22),28,fill=(0,0,0,110))
    shadow=shadow.filter(ImageFilter.GaussianBlur(12))
    layer.alpha_composite(shadow,(x-20,y-10)); layer.alpha_composite(card.convert("RGBA"),(x,y))
    bg.alpha_composite(layer)
    return bg.convert("RGB")


def source_frame(gifs,stills,key,q,center=(.5,.5),scale0=1.03,scale1=1.14):
    if key in gifs:
        fs=gifs[key]; idx=min(len(fs)-1,int(q*(len(fs)-1)))
        return zoom_crop(fs[idx],scale0+(scale1-scale0)*q,center)
    return zoom_crop(stills[key],scale0+(scale1-scale0)*q,center)


def render(sec,total,gifs,stills,formation,sprites):
    # 13 macro scenes, with internal movement/cuts. The first 12 seconds are especially fast.
    cuts=[0,4.5,9,14,19,24,29,34,39,44,49,54,59,total]
    i=max(0,min(len(cuts)-2,next((j for j in range(len(cuts)-1) if cuts[j]<=sec<cuts[j+1]),len(cuts)-2)))
    a,b=cuts[i],cuts[i+1]; q=(sec-a)/(b-a)

    # change source/crop halfway through most scenes to keep visual rhythm alive
    half=q<.5
    qq=(q*2) if half else ((q-.5)*2)

    if i==0:
        img=source_frame(gifs,stills,"gif2018",q,(.50,.50),1.04,1.15)
        d=ImageDraw.Draw(img)
        if q<.30: text_center(d,"WHY SO WINDY?",145,82)
        subtitle(d,"A NOR'EASTER CAN FEEL LIKE A WALL OF WIND")
        if .25<q<.92:
            img=place_owl(img,sprites,3,45,1120,450,bob=8*math.sin(q*math.pi*3))
        credit(d)

    elif i==1:
        key="geo2018a" if half else "geo2018b"
        img=source_frame(gifs,stills,key,qq,(.48,.50),1.02,1.18)
        d=ImageDraw.Draw(img); subtitle(d,"FROM SPACE: A GIANT SPINNING COMMA")
        if q>.58: img=place_owl(img,sprites,0,620,1135,420,flip=True)
        credit(d)

    elif i==2:
        base=gifs["gif2018"][int(qq*(len(gifs["gif2018"])-1))]
        img=graphic_card(base,formation,"jet" if half else "full",qq)
        d=ImageDraw.Draw(img); subtitle(d,"COLD CANADIAN AIR DIVES SOUTH")
        if half: img=place_owl(img,sprites,1,35,1135,420)
        d=ImageDraw.Draw(img); credit(d,"NOAA/JPL-Caltech graphic")

    elif i==3:
        base=gifs["gif2020"][int(qq*(len(gifs["gif2020"])-1))]
        img=graphic_card(base,formation,"wind" if half else "full",qq)
        d=ImageDraw.Draw(img); subtitle(d,"THE ATLANTIC STAYS MUCH MILDER")
        if not half: img=place_owl(img,sprites,5,610,1130,430,flip=True)
        d=ImageDraw.Draw(img); credit(d,"NOAA/JPL-Caltech graphic")

    elif i==4:
        img=source_frame(gifs,stills,"thermal",q,(.47,.55),1.04,1.28)
        d=ImageDraw.Draw(img)
        pulse=65+50*abs(math.sin(q*math.pi*2))
        d.ellipse((500-pulse,940-pulse,500+pulse,940+pulse),outline=YELLOW,width=18)
        text_center(d,"LOW PRESSURE DEEPENS",230,55,fill=YELLOW)
        subtitle(d,"TEMPERATURE CONTRAST FEEDS THE STORM")
        credit(d)

    elif i==5:
        key="geo2018b" if half else "thermal"
        img=source_frame(gifs,stills,key,qq,(.46,.54),1.06,1.19)
        d=ImageDraw.Draw(img)
        for j in range(4):
            y=630+j*190; arrow(d,90,y,600+int(150*qq),y+55,BLUE if j!=1 else ORANGE,18)
        subtitle(d,"AIR RUSHES TOWARD THE LOW")
        if q>.55: img=place_owl(img,sprites,1,650,1155,390,flip=True)
        d=ImageDraw.Draw(img); credit(d)

    elif i==6:
        img=source_frame(gifs,stills,"gif2018",q,(.50,.51),1.05,1.18)
        d=ImageDraw.Draw(img)
        for k in range(3):
            off=k*85
            curved_arrow(d,(220-off,500-off,880+off,1260+off),195,515,BLUE,14)
        subtitle(d,"EARTH'S ROTATION BENDS THE FLOW")
        if q<.55: img=place_owl(img,sprites,2,55,1130,405)
        d=ImageDraw.Draw(img); credit(d)

    elif i==7:
        img=source_frame(gifs,stills,"thermal",q,(.48,.54),1.04,1.19)
        d=ImageDraw.Draw(img)
        cx,cy=520,930
        gap=95-int(45*q)
        for r0 in (190,190+gap,190+2*gap,190+3*gap):
            d.ellipse((cx-r0,cy-r0,cx+r0,cy+r0),outline=BLUE,width=10)
        subtitle(d,"PACKED PRESSURE LINES = STEEP GRADIENT")
        credit(d)

    elif i==8:
        key="geo2018c" if half else "geo2018b"
        img=source_frame(gifs,stills,key,qq,(.50,.52),1.04,1.18)
        d=ImageDraw.Draw(img)
        speed=320+int(240*q)
        for j,y in enumerate((640,860,1080,1300)):
            x=60+int((q*300+j*90)%300)
            arrow(d,x,y,min(1020,x+speed),y-35,ORANGE if j==1 else BLUE,20)
        subtitle(d,"STRONGER GRADIENT = STRONGER WIND")
        if q>.58: img=place_owl(img,sprites,5,50,1130,410)
        d=ImageDraw.Draw(img); credit(d)

    elif i==9:
        base=gifs["gif2020"][int(qq*(len(gifs["gif2020"])-1))]
        img=graphic_card(base,formation,"wind",qq)
        d=ImageDraw.Draw(img)
        text_center(d,"NORTHEAST → COAST",245,55,fill=YELLOW)
        subtitle(d,"THAT'S WHERE “NOR'EASTER” GETS ITS NAME")
        if q<.55: img=place_owl(img,sprites,1,40,1130,420)
        d=ImageDraw.Draw(img); credit(d,"NOAA/JPL-Caltech graphic")

    elif i==10:
        key="gif2020" if half else "geo2018c"
        img=source_frame(gifs,stills,key,qq,(.50,.52),1.03,1.17)
        d=ImageDraw.Draw(img)
        label=("HEAVY SNOW" if q<.34 else ("COASTAL FLOODING" if q<.67 else "HUGE WAVES"))
        text_center(d,label,230,64,fill=YELLOW)
        subtitle(d,"ATLANTIC MOISTURE ADDS THE IMPACTS")
        credit(d)

    elif i==11:
        key="geo2018a" if half else "gif2018"
        img=source_frame(gifs,stills,key,qq,(.50,.51),1.04,1.16)
        d=ImageDraw.Draw(img)
        text_center(d,"THE WIND ISN'T SEPARATE",230,52)
        subtitle(d,"IT'S THE STORM TRYING TO BALANCE PRESSURE")
        if q>.45: img=place_owl(img,sprites,2,610,1120,430,flip=True)
        d=ImageDraw.Draw(img); credit(d)

    else:
        img=source_frame(gifs,stills,"gif2018",q,(.51,.51),1.07,1.18)
        d=ImageDraw.Draw(img)
        if q<.55:
            text_center(d,"BIG PRESSURE DIFFERENCE",230,54,fill=YELLOW)
        else:
            text_center(d,"→ WIND STRAIGHT AT THE COAST",230,48,fill=YELLOW)
        subtitle(d,"THAT'S THE NOR'EASTER ENGINE")
        img=place_owl(img,sprites,0,55,1110,455,bob=7*math.sin(q*math.pi*2))
        d=ImageDraw.Draw(img); credit(d)

    return img.convert("RGB")


def main():
    out=Path("output"); out.mkdir(exist_ok=True)
    build=Path("build"); build.mkdir(exist_ok=True)

    sprites=load_owl_sprites()
    gifs={}
    stills={}
    for key in ("gif2018","gif2020"):
        try: gifs[key]=load_gif(URLS[key])
        except Exception:
            gifs[key]=[load_image(URLS["geo2018a"])]
    fallback=load_image(URLS["thermal"])
    for key in ("thermal","geo2018a","geo2018b","geo2018c"):
        try:
            stills[key]=load_image(URLS[key])
        except Exception as exc:
            print(f"WARNING: {key} failed to load: {exc}; using NOAA thermal fallback")
            stills[key]=fallback.copy()
    try:
        formation=load_image(URLS["formation"])
    except Exception as exc:
        print(f"WARNING: formation graphic failed: {exc}; using thermal fallback")
        formation=fallback.copy()

    # Natural voice first; only a small automatic speed adjustment is allowed.
    wav=build/"voice.wav"
    dur=generate_narration(SCRIPT,wav,voice="af_heart",speed=1.0)
    target_voice=64.6
    needed=max(.92,min(1.05,dur/target_voice))
    if abs(needed-1.0)>.015:
        dur=generate_narration(SCRIPT,wav,voice="af_heart",speed=needed)

    data,sr=sf.read(wav); dur=len(data)/sr
    total=max(65.5,min(69.0,dur+1.0))

    raw=build/"full_raw.mp4"
    ff=subprocess.Popen([
        "ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}",
        "-r",str(FPS),"-i","-","-an","-c:v","libx264","-preset","veryfast",
        "-crf","19","-pix_fmt","yuv420p",str(raw)
    ],stdin=subprocess.PIPE)

    for n in range(int(total*FPS)):
        frame=render(n/FPS,total,gifs,stills,formation,sprites)
        ff.stdin.write(frame.tobytes())
    ff.stdin.close()
    if ff.wait()!=0: raise SystemExit("visual render failed")

    # Natural narration processing + very subtle storm ambience.
    final=out/"PaperKnowledge_Noreaster_Full_Preview.mp4"
    subprocess.run([
        "ffmpeg","-y","-i",str(raw),"-i",str(wav),
        "-f","lavfi","-t",f"{total:.3f}","-i","anoisesrc=color=pink:amplitude=0.010:sample_rate=48000",
        "-filter_complex",
        "[1:a]highpass=f=75,lowpass=f=12500,"
        "equalizer=f=3200:t=q:w=1.1:g=1.6,"
        "acompressor=threshold=-18dB:ratio=2.2:attack=18:release=140,"
        "loudnorm=I=-16:TP=-1.3:LRA=6[v];"
        "[2:a]highpass=f=160,lowpass=f=1800,volume=0.10[w];"
        "[v][w]amix=inputs=2:duration=longest:dropout_transition=0[m];"
        "[m]loudnorm=I=-16:TP=-1.3:LRA=6[a]",
        "-map","0:v:0","-map","[a]","-c:v","copy","-c:a","aac","-b:a","192k",
        "-ar","48000","-t",f"{total:.3f}",str(final)
    ],check=True)

    # QA
    probe=json.loads(subprocess.check_output([
        "ffprobe","-v","error","-show_streams","-show_format","-of","json",str(final)
    ]))
    v=[s for s in probe["streams"] if s.get("codec_type")=="video"][0]
    a=[s for s in probe["streams"] if s.get("codec_type")=="audio"]
    actual=float(probe["format"]["duration"])
    report={
        "ok": bool(a) and int(v["width"])==1080 and int(v["height"])==1920 and actual>=65,
        "duration_seconds":round(actual,3),
        "resolution":f"{v['width']}x{v['height']}",
        "voice":"af_heart",
        "mascot_poses":len(sprites),
        "published":False,
    }
    (out/"full_qa.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    if not report["ok"]: raise SystemExit("QA failed")


if __name__=="__main__":
    main()
