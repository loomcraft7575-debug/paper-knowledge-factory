from __future__ import annotations

import io, json, math, subprocess, sys, urllib.request
from collections import deque
from pathlib import Path
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from tts import generate_narration

W,H,FPS=1080,1920,20
BG=(242,236,221); INK=(25,30,38); BLUE=(52,118,222); ORANGE=(244,127,75); YELLOW=(249,204,72); WHITE=(255,255,255)

def font(size,bold=False):
    ps=[
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in ps:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def fetch_image(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 PaperKnowledge/1.0"})
    with urllib.request.urlopen(req,timeout=25) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")

def fit_vertical(im,center=(.5,.5)):
    return ImageOps.fit(im.convert("RGB"),(W,H),method=Image.Resampling.LANCZOS,centering=center)

def zoom(im,q,center=(.5,.5)):
    base=fit_vertical(im,center)
    s=1.03+.13*q
    nw,nh=int(W*s),int(H*s)
    z=base.resize((nw,nh),Image.Resampling.LANCZOS)
    cx=int(center[0]*nw); cy=int(center[1]*nh)
    left=max(0,min(nw-W,cx-W//2)); top=max(0,min(nh-H,cy-H//2))
    return z.crop((left,top,left+W,top+H))

def subtitle(d,text,y=1570,size=48,max_width=900):
    f=font(size,True); words=text.strip().split(); lines=[]; cur=""
    for w in words:
        trial=(cur+" "+w).strip()
        b=d.textbbox((0,0),trial,font=f,stroke_width=5)
        if cur and b[2]-b[0]>max_width:
            lines.append(cur); cur=w
        else: cur=trial
    if cur: lines.append(cur)
    lines=lines[:2]
    sy=y-(len(lines)-1)*32
    for i,line in enumerate(lines):
        b=d.textbbox((0,0),line,font=f,stroke_width=5)
        x=(W-(b[2]-b[0]))//2
        d.text((x,sy+i*64),line,font=f,fill=WHITE,stroke_width=5,stroke_fill=INK)

def text_center(d,text,y,size,fill=WHITE):
    f=font(size,True); b=d.textbbox((0,0),text,font=f,stroke_width=5)
    d.text(((W-(b[2]-b[0]))//2,y),text,font=f,fill=fill,stroke_width=5,stroke_fill=INK)

def arrow(d,x1,y1,x2,y2,color=BLUE,width=18):
    d.line((x1,y1,x2,y2),fill=color,width=width)
    a=math.atan2(y2-y1,x2-x1); L=30
    for q in (2.55,-2.55):
        d.line((x2,y2,x2+L*math.cos(a+q),y2+L*math.sin(a+q)),fill=color,width=width)

def paper_scene(text,q,index):
    img=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(img)
    for y in range(0,H,30):
        d.line((0,y,W,y),fill=(150,140,120),width=1)
    # Animated technical diagram that varies by beat.
    cx,cy=W//2,870
    if index%4==0:
        for j in range(4):
            r=130+j*90+int(20*math.sin(q*math.pi*2+j))
            d.ellipse((cx-r,cy-r,cx+r,cy+r),outline=BLUE if j%2==0 else ORANGE,width=13)
        arrow(d,140,1180,870,760,ORANGE,20)
    elif index%4==1:
        for j in range(5):
            x=120+j*190
            h=220+int((j+1)*70*q)
            d.rounded_rectangle((x,1180-h,x+110,1180),24,fill=BLUE if j%2==0 else ORANGE)
        arrow(d,150,1350,920,1350,YELLOW,18)
    elif index%4==2:
        pts=[]
        for j in range(8):
            x=90+j*130; y=900+int(180*math.sin(j*.8+q*math.pi*2))
            pts.append((x,y))
        d.line(pts,fill=BLUE,width=20)
        for p in pts: d.ellipse((p[0]-18,p[1]-18,p[0]+18,p[1]+18),fill=ORANGE)
    else:
        for j in range(6):
            y=520+j*170
            arrow(d,100+int(80*q),y,880-int(60*q),y-25,BLUE if j%2==0 else ORANGE,18)
    text_center(d,text[:34].upper(),260,54,fill=YELLOW)
    return img

def flood_transparency(crop):
    arr=np.array(crop.convert("RGBA")); rgb=arr[:,:,:3].astype(np.int16); h,w=rgb.shape[:2]
    corners=np.vstack([rgb[:12,:12].reshape(-1,3),rgb[:12,-12:].reshape(-1,3),rgb[-12:,:12].reshape(-1,3),rgb[-12:,-12:].reshape(-1,3)])
    bg=np.median(corners,axis=0); dist=np.sqrt(((rgb-bg)**2).sum(axis=2)); cand=dist<42
    seen=np.zeros((h,w),dtype=bool); q=deque()
    for x in range(w):
        for y in (0,h-1):
            if cand[y,x] and not seen[y,x]: seen[y,x]=True; q.append((y,x))
    for y in range(h):
        for x in (0,w-1):
            if cand[y,x] and not seen[y,x]: seen[y,x]=True; q.append((y,x))
    while q:
        y,x=q.popleft()
        for yy,xx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
            if 0<=yy<h and 0<=xx<w and cand[yy,xx] and not seen[yy,xx]:
                seen[yy,xx]=True; q.append((yy,xx))
    alpha=Image.fromarray(np.where(seen,0,255).astype("uint8")).filter(ImageFilter.GaussianBlur(1.1))
    out=Image.fromarray(arr); out.putalpha(alpha); bbox=out.getchannel("A").getbbox()
    return out.crop(bbox) if bbox else out

def owl_sprites():
    sheet=Image.open("assets/mascot/action-poses.png").convert("RGB"); sw,sh=sheet.size; cw=sw//3
    rows=((0,int(sh*.43)),(int(sh*.48),int(sh*.91))); out=[]
    for ya,yb in rows:
        for col in range(3): out.append(flood_transparency(sheet.crop((col*cw,ya,(col+1)*cw,yb))))
    return out

def place_owl(img,sprites,idx,x,y,height=400,flip=False):
    sp=sprites[idx%len(sprites)].copy(); scale=height/sp.height
    sp=sp.resize((max(1,int(sp.width*scale)),height),Image.Resampling.LANCZOS)
    if flip: sp=sp.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    img=img.convert("RGBA"); a=sp.getchannel("A")
    shadow=Image.new("RGBA",sp.size,(0,0,0,50)); shadow.putalpha(a.filter(ImageFilter.GaussianBlur(11)))
    img.alpha_composite(shadow,(x+12,y+16)); img.alpha_composite(sp,(x,y))
    return img.convert("RGB")

def main(job_path):
    job=json.loads(Path(job_path).read_text(encoding="utf-8"))
    job_id=job["job_id"]; script=job["script"]; beats=job["beats"]
    if len(beats)<13: beats=(beats*13)[:13]
    urls=job.get("visual_urls",[])[:8]
    visuals=[]
    for u in urls:
        try: visuals.append(fetch_image(u))
        except Exception as e: print("visual fetch failed",u,e)
    sprites=owl_sprites()

    build=Path("build")/job_id; build.mkdir(parents=True,exist_ok=True)
    out=Path("output"); out.mkdir(exist_ok=True)
    wav=build/"voice.wav"
    dur=generate_narration(script,wav,voice=job.get("voice","af_heart"),speed=1.0)
    target=64.5
    speed=max(.94,min(1.08,dur/target))
    if abs(speed-1.0)>.015: dur=generate_narration(script,wav,voice=job.get("voice","af_heart"),speed=speed)
    data,sr=sf.read(wav); dur=len(data)/sr
    total=max(65.0,min(72.0,dur+1.0))

    raw=build/"raw.mp4"
    ff=subprocess.Popen([
        "ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-",
        "-an","-c:v","libx264","-preset","veryfast","-crf","23","-pix_fmt","yuv420p",str(raw)
    ],stdin=subprocess.PIPE)

    seg=total/13
    for n in range(int(total*FPS)):
        sec=n/FPS; idx=min(12,int(sec/seg)); q=(sec-idx*seg)/seg
        if visuals and idx%3!=1:
            im=visuals[idx%len(visuals)]
            img=zoom(im,q,center=(.48+(idx%3)*.02,.50))
            d=ImageDraw.Draw(img)
            if idx==0 and q<.45: text_center(d,job["question"][:36].upper(),165,58,fill=YELLOW)
        else:
            img=paper_scene(beats[idx],q,idx); d=ImageDraw.Draw(img)
        subtitle(d,beats[idx])
        if idx in (0,3,6,9,12):
            img=place_owl(img,sprites,idx,55 if idx%2==0 else 640,1120,420,flip=idx%2==1)
        ff.stdin.write(img.convert("RGB").tobytes())
    ff.stdin.close()
    if ff.wait()!=0: raise SystemExit("visual render failed")

    final=out/f"{job_id}.mp4"
    subprocess.run([
        "ffmpeg","-y","-i",str(raw),"-i",str(wav),
        "-f","lavfi","-t",f"{total:.3f}","-i","anoisesrc=color=pink:amplitude=0.008:sample_rate=48000",
        "-filter_complex",
        "[1:a]highpass=f=75,lowpass=f=12500,equalizer=f=3200:t=q:w=1.1:g=1.4,"
        "acompressor=threshold=-18dB:ratio=2.1:attack=18:release=140,loudnorm=I=-16:TP=-1.3:LRA=6[v];"
        "[2:a]highpass=f=160,lowpass=f=1800,volume=0.08[w];"
        "[v][w]amix=inputs=2:duration=longest:dropout_transition=0[m];[m]loudnorm=I=-16:TP=-1.3:LRA=6[a]",
        "-map","0:v:0","-map","[a]","-c:v","copy","-c:a","aac","-b:a","160k","-ar","48000","-t",f"{total:.3f}",str(final)
    ],check=True)
    qa={"ok":True,"job_id":job_id,"duration_seconds":round(total,3),"resolution":"1080x1920","sources":job.get("sources",[])}
    (out/f"{job_id}.json").write_text(json.dumps(qa,indent=2),encoding="utf-8")
    print(json.dumps(qa))

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("Usage: python src/batch_video.py jobs/batch/<job>.json")
    main(sys.argv[1])
