from __future__ import annotations

import math
import subprocess
from pathlib import Path

import cv2
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from tts import generate_narration

W, H = 1080, 1920
FPS = 30
BG = (246, 240, 225)
INK = (30, 34, 40)
BLUE = (48, 116, 220)
PALE_BLUE = (215, 233, 255)
CORAL = (234, 98, 78)
PALE_CORAL = (255, 225, 216)
YELLOW = (247, 198, 67)
WHITE = (255,255,255)

OWL_CACHE = {}


def font(size:int,bold:bool=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p,size=size)
    return ImageFont.load_default()


def clamp(x): return max(0.0,min(1.0,x))
def ease(x):
    x = clamp(x)
    return 1-(1-x)**3


def texture(img):
    d = ImageDraw.Draw(img)
    for y in range(0,H,30):
        d.line((0,y,W,y),fill=(126,115,95,16),width=1)
    for x in range(20,W,80):
        d.ellipse((x,1800+(x%3)*8,x+2,1802+(x%3)*8),fill=(100,90,75,18))


def brand(d):
    d.text((48,40),"PAPER KNOWLEDGE",font=font(30,True),fill=(94,94,96))


def text_center(d,text,y,size,fill=INK):
    f=font(size,True)
    box=d.textbbox((0,0),text,font=f)
    d.text(((W-(box[2]-box[0]))//2,y),text,font=f,fill=fill)


def arrow(d,x1,y1,x2,y2,fill=BLUE,width=18):
    d.line((x1,y1,x2,y2),fill=fill,width=width)
    a=math.atan2(y2-y1,x2-x1)
    L=32
    for dd in (2.55,-2.55):
        d.line((x2,y2,x2+L*math.cos(a+dd),y2+L*math.sin(a+dd)),fill=fill,width=width)


def caption(d,text,y,accent=YELLOW):
    f=font(58,True)
    b=d.textbbox((0,0),text,font=f)
    tw=b[2]-b[0]
    x=(W-tw)//2
    d.rounded_rectangle((x-24,y-13,x+tw+24,y+64),18,fill=accent)
    d.text((x,y),text,font=f,fill=INK)


def owl_cutout(idx:int,max_h=470):
    key=(idx,max_h)
    if key in OWL_CACHE:
        return OWL_CACHE[key].copy()
    poses=sorted(Path("assets/mascot").glob("pose*.png"))
    if not poses:
        return None
    bgr=cv2.imread(str(poses[idx%len(poses)]),cv2.IMREAD_COLOR)
    h,w=bgr.shape[:2]

    # Seed GrabCut: borders are background, central owl area is foreground.
    mask=np.full((h,w),cv2.GC_PR_BGD,np.uint8)
    mx,my=int(w*.08),int(h*.08)
    mask[:my,:]=cv2.GC_BGD
    mask[h-my:,:]=cv2.GC_BGD
    mask[:,:mx]=cv2.GC_BGD
    mask[:,w-mx:]=cv2.GC_BGD

    cv2.ellipse(mask,(w//2,int(h*.57)),(int(w*.30),int(h*.38)),0,0,360,cv2.GC_PR_FGD,-1)
    cv2.rectangle(mask,(int(w*.38),int(h*.28)),(int(w*.62),int(h*.78)),cv2.GC_FGD,-1)

    bgd=np.zeros((1,65),np.float64)
    fgd=np.zeros((1,65),np.float64)
    cv2.grabCut(bgr,mask,None,bgd,fgd,5,cv2.GC_INIT_WITH_MASK)
    alpha=np.where((mask==cv2.GC_FGD)|(mask==cv2.GC_PR_FGD),255,0).astype("uint8")
    alpha=cv2.GaussianBlur(alpha,(7,7),0)

    rgba=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGBA)
    rgba[:,:,3]=alpha
    pil=Image.fromarray(rgba)

    bbox=pil.getchannel("A").getbbox()
    if bbox:
        pil=pil.crop(bbox)
    scale=max_h/pil.height
    pil=pil.resize((max(1,int(pil.width*scale)),max_h),Image.Resampling.LANCZOS)
    OWL_CACHE[key]=pil
    return pil.copy()


def place_owl(img,idx,x,y,max_h=470,flip=False):
    owl=owl_cutout(idx,max_h)
    if owl is None:
        return
    if flip:
        owl=owl.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

    # sticker outline from alpha
    a=owl.getchannel("A")
    outline=a.filter(ImageFilter.MaxFilter(21))
    sticker=Image.new("RGBA",owl.size,(255,252,242,0))
    sticker.putalpha(outline)
    shadow=Image.new("RGBA",owl.size,(0,0,0,0))
    shadow.putalpha(a.filter(ImageFilter.GaussianBlur(12)))
    dark=Image.new("RGBA",owl.size,(0,0,0,48))
    dark.putalpha(shadow.getchannel("A"))

    img.alpha_composite(dark,(x+16,y+20))
    img.alpha_composite(sticker,(x,y))
    img.alpha_composite(owl,(x,y))


def coast(d):
    pts=[(760,330),(725,460),(756,590),(710,720),(744,860),(700,1010),(738,1160),(700,1310),(752,1470)]
    d.line(pts,fill=INK,width=18)
    d.text((790,350),"EAST COAST",font=font(32,True),fill=INK)


def scene_hook(img,t):
    d=ImageDraw.Draw(img)
    brand(d)
    text_center(d,"WHY SO WINDY?",125,88,BLUE)
    coast(d)
    for i,yy in enumerate((470,650,830,1010,1190)):
        phase=(t*430+i*180)%980
        x=-300+phase
        d.arc((x,yy-90,x+500,yy+100),188,352,fill=BLUE,width=25)
    d.line((906,1190,842,1505),fill=(100,76,54),width=30)
    for yy in (1270,1360,1440):
        d.line((878,yy,765,yy-72),fill=(77,123,66),width=28)

    place_owl(img,0,60,1000,500)
    caption(d,"WALL-LIKE WINDS",1495)


def scene_cold(img,t):
    d=ImageDraw.Draw(img)
    brand(d)
    d.rounded_rectangle((70,250,1010,700),55,fill=PALE_BLUE)
    d.text((140,365),"COLD AIR",font=font(96,True),fill=BLUE)
    d.text((143,485),"FROM CANADA",font=font(54,True),fill=BLUE)

    for i in range(5):
        xx=180+i*160
        yy=760+int(((t*480+i*120)%520))
        arrow(d,xx,yy-150,xx,yy,BLUE,20)

    place_owl(img,1,590,980,500,flip=True)
    caption(d,"COLD AIR RUSHES SOUTH",1495,PALE_BLUE)


def scene_meet(img,t):
    d=ImageDraw.Draw(img)
    brand(d)

    # torn-paper style opposing air masses
    left=int(-280+300*ease(t))
    right=int(840-300*ease(t))
    d.rounded_rectangle((left,330,left+560,1180),55,fill=PALE_BLUE)
    d.rounded_rectangle((right,330,right+560,1180),55,fill=PALE_CORAL)
    d.text((left+105,470),"COLD",font=font(84,True),fill=BLUE)
    d.text((right+70,470),"MILD",font=font(84,True),fill=CORAL)

    arrow(d,240,900,490,900,BLUE,25)
    arrow(d,840,900,590,900,CORAL,25)
    r=45+70*abs(math.sin(t*math.pi))
    d.ellipse((540-r,900-r,540+r,900+r),outline=YELLOW,width=20)

    place_owl(img,2,80,1060,470)
    caption(d,"COLD MEETS MILD",1495,YELLOW)


def scene_pressure(img,t):
    d=ImageDraw.Draw(img)
    brand(d)

    # No header bar: the diagram is the headline.
    gap=int(115-68*ease(t))
    cx=570
    for i in range(6):
        x=cx-gap*2+i*gap
        d.arc((x-330,310,x+330,1260),72,288,fill=BLUE,width=14)

    d.ellipse((475,650,655,830),outline=BLUE,width=17)
    d.text((535,675),"L",font=font(96,True),fill=BLUE)

    sp=270+int(250*ease(t))
    for i,yy in enumerate((510,1010,1220)):
        x=int(100+((t*880+i*240)%760))
        arrow(d,x,yy,min(x+sp,990),yy-8,CORAL if i==1 else BLUE,20)

    place_owl(img,4,70,1090,500)
    if t<.48:
        caption(d,"LOW PRESSURE DEEPENS",1495,PALE_BLUE)
    else:
        caption(d,"TIGHTER = FASTER",1495,YELLOW)


def main():
    out=Path("output"); out.mkdir(exist_ok=True)
    build=Path("build"); build.mkdir(exist_ok=True)

    script=(
        "A nor'easter can hit the East Coast with wall-like winds. "
        "Cold Canadian air meets the warmer Atlantic. "
        "That contrast deepens low pressure. Tighter pressure lines mean faster wind."
    )
    narration=build/"prototype.wav"
    dur=generate_narration(script,narration,voice="af_sky",speed=1.0)

    if dur>12.2:
        tempo=min(1.12,dur/11.7)
        sped=build/"prototype_sped.wav"
        subprocess.run(["ffmpeg","-y","-i",str(narration),"-filter:a",f"atempo={tempo:.4f}",str(sped)],check=True)
        narration=sped
        data,sr=sf.read(narration); dur=len(data)/sr

    total=max(11.4,min(dur+0.25,12.0))
    frames=int(total*FPS)

    raw=build/"prototype_video.mp4"
    ff=subprocess.Popen([
        "ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}",
        "-r",str(FPS),"-i","-","-an","-c:v","libx264","-preset","veryfast",
        "-crf","19","-pix_fmt","yuv420p",str(raw)
    ],stdin=subprocess.PIPE)

    cuts=[0.0,0.25,0.46,0.69,1.0]
    for n in range(frames):
        p=(n/FPS)/total
        img=Image.new("RGBA",(W,H),BG+(255,))
        texture(img)
        if p<cuts[1]:
            scene_hook(img,(p-cuts[0])/(cuts[1]-cuts[0]))
        elif p<cuts[2]:
            scene_cold(img,(p-cuts[1])/(cuts[2]-cuts[1]))
        elif p<cuts[3]:
            scene_meet(img,(p-cuts[2])/(cuts[3]-cuts[2]))
        else:
            scene_pressure(img,(p-cuts[3])/(cuts[4]-cuts[3]))
        ff.stdin.write(img.convert("RGB").tobytes())

    ff.stdin.close()
    if ff.wait()!=0:
        raise SystemExit("frame render failed")

    final=out/"paper_knowledge_prototype.mp4"
    subprocess.run([
        "ffmpeg","-y","-i",str(raw),"-i",str(narration),
        "-filter_complex","[1:a]loudnorm=I=-16:TP=-1.5:LRA=7[a]",
        "-map","0:v:0","-map","[a]","-c:v","copy","-c:a","aac","-b:a","160k",
        "-ar","48000","-shortest",str(final)
    ],check=True)
    print(final)


if __name__=="__main__":
    main()
