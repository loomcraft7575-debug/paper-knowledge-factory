from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from textwrap import wrap

import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

from tts import generate_narration

W, H = 1080, 1920
BG = (246, 241, 226)
INK = (32, 35, 41)
BLUE = (70, 120, 210)
RED = (214, 90, 78)
GRAY = (115, 120, 125)
WHITE = (255, 255, 255)


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def centered_text(draw, text, y, size=64, bold=False, fill=INK, max_chars=28):
    lines = wrap(text, width=max_chars)
    f = font(size, bold)
    line_h = int(size * 1.22)
    for i, line in enumerate(lines):
        box = draw.textbbox((0, 0), line, font=f)
        x = (W - (box[2] - box[0])) // 2
        draw.text((x, y + i * line_h), line, font=f, fill=fill)
    return y + len(lines) * line_h


def arrow(draw, start, end, fill=INK, width=14):
    draw.line([start, end], fill=fill, width=width)
    ang = math.atan2(end[1]-start[1], end[0]-start[0])
    length = 34
    for delta in (2.55, -2.55):
        p = (end[0] + length * math.cos(ang + delta), end[1] + length * math.sin(ang + delta))
        draw.line([end, p], fill=fill, width=width)


def draw_diagram(draw, kind: str):
    top, bottom = 520, 1350
    cx = W // 2
    if kind == "hook":
        draw.ellipse((360, 650, 720, 1010), outline=BLUE, width=18)
        draw.text((470, 735), "L", font=font(140, True), fill=BLUE)
        for a in range(0, 360, 60):
            rad = math.radians(a)
            p1 = (cx + int(250*math.cos(rad)), 830 + int(250*math.sin(rad)))
            p2 = (cx + int(340*math.cos(rad+0.35)), 830 + int(340*math.sin(rad+0.35)))
            arrow(draw, p1, p2, BLUE, 10)
    elif kind == "east_coast_low":
        draw.line((670, top, 640, bottom), fill=INK, width=18)
        draw.arc((590, 700, 940, 1050), 30, 330, fill=BLUE, width=18)
        draw.text((725, 775), "L", font=font(130, True), fill=BLUE)
        centered_text(draw, "LOW PRESSURE", 1110, 56, True, BLUE)
    elif kind == "air_masses":
        draw.rounded_rectangle((70, 650, 485, 1110), 45, fill=(220, 234, 255))
        draw.rounded_rectangle((595, 650, 1010, 1110), 45, fill=(255, 224, 216))
        draw.text((145, 760), "COLD", font=font(82, True), fill=BLUE)
        draw.text((650, 760), "MILD", font=font(82, True), fill=RED)
        arrow(draw, (300, 1030), (520, 1030), BLUE, 16)
        arrow(draw, (780, 1030), (560, 1030), RED, 16)
        centered_text(draw, "temperature contrast", 1190, 50, True)
    elif kind == "pressure":
        draw.ellipse((100, 700, 370, 970), outline=GRAY, width=16)
        draw.ellipse((710, 700, 980, 970), outline=BLUE, width=16)
        draw.text((178, 750), "H", font=font(120, True), fill=GRAY)
        draw.text((792, 750), "L", font=font(120, True), fill=BLUE)
        arrow(draw, (395, 835), (685, 835), INK, 18)
        centered_text(draw, "HIGH → LOW", 1080, 60, True)
    elif kind == "gradient":
        xs = [190, 350, 475, 565, 630, 680]
        for x in xs:
            draw.line((x, 620, x, 1130), fill=BLUE, width=10)
        arrow(draw, (180, 1250), (850, 1250), RED, 22)
        centered_text(draw, "closer isobars = stronger wind", 1360, 45, True)
    elif kind == "rotation":
        draw.ellipse((350, 650, 730, 1030), outline=BLUE, width=18)
        draw.text((468, 735), "L", font=font(140, True), fill=BLUE)
        for a in (30, 120, 210, 300):
            rad = math.radians(a)
            start = (cx + int(300*math.cos(rad)), 840 + int(300*math.sin(rad)))
            end = (cx + int(300*math.cos(rad+0.55)), 840 + int(300*math.sin(rad+0.55)))
            arrow(draw, start, end, BLUE, 12)
        centered_text(draw, "COUNTERCLOCKWISE", 1200, 48, True)
    elif kind == "northeast":
        draw.line((650, 600, 650, 1260), fill=INK, width=18)
        draw.text((690, 610), "COAST", font=font(46, True), fill=INK)
        arrow(draw, (220, 760), (610, 1030), BLUE, 24)
        draw.text((155, 650), "NE", font=font(86, True), fill=BLUE)
        centered_text(draw, "winds blow toward the coast", 1320, 48, True)
    elif kind == "comparison":
        draw.rounded_rectangle((65, 610, 505, 1210), 40, outline=RED, width=12)
        draw.rounded_rectangle((575, 610, 1015, 1210), 40, outline=BLUE, width=12)
        centered_text(draw, "HURRICANE", 665, 50, True, RED, 16)
        draw.text((125, 830), "warm ocean\nheat", font=font(55, True), fill=RED)
        draw.text((635, 830), "NOR'EASTER\n\ntemperature\ncontrast", font=font(50, True), fill=BLUE)
    else:
        centered_text(draw, "PAPER KNOWLEDGE", 780, 72, True)


def place_mascot(canvas: Image.Image, pose_index: int):
    poses = sorted(Path("assets/mascot").glob("*.png"))
    if not poses:
        return
    path = poses[pose_index % len(poses)]
    mascot = Image.open(path).convert("RGBA")
    mascot.thumbnail((390, 390))
    x = 40 if pose_index % 2 == 0 else W - mascot.width - 40
    y = H - mascot.height - 60
    canvas.alpha_composite(mascot, (x, y))


def render_scene(scene: dict, title: str, index: int, output: Path):
    img = Image.new("RGBA", (W, H), BG + (255,))
    draw = ImageDraw.Draw(img)
    draw.text((45, 40), "PAPER KNOWLEDGE", font=font(38, True), fill=GRAY)
    centered_text(draw, title, 130, 68, True, INK, 25)
    draw_diagram(draw, scene.get("diagram", ""))
    caption = scene.get("caption", "")
    y = 1450
    draw.rounded_rectangle((60, y-35, W-60, H-120), 38, fill=(255,255,255,235))
    centered_text(draw, caption, y, 52, True, INK, 30)
    place_mascot(img, int(scene.get("mascot", index)))
    output.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(output, quality=95)


def run(cmd):
    print("+", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, check=True)


def ffprobe(path: Path) -> dict:
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ])
    return json.loads(raw)


def main(job_path: str):
    job_file = Path(job_path)
    job = json.loads(job_file.read_text(encoding="utf-8"))
    work = Path("build")
    frames = work / "frames"
    out = Path("output")
    out.mkdir(exist_ok=True)
    frames.mkdir(parents=True, exist_ok=True)

    narration = work / "narration.wav"
    speed = float(job.get("voice_speed", 0.95))
    duration = generate_narration(job["script"], narration, voice=job.get("voice", "af_sky"), speed=speed)

    target = 72.0
    if duration < 65 or duration > 120:
        adjusted = max(0.75, min(1.20, speed * duration / target))
        print(f"Narration {duration:.1f}s outside target; regenerating at speed {adjusted:.3f}")
        duration = generate_narration(job["script"], narration, voice=job.get("voice", "af_sky"), speed=adjusted)

    if not 65 <= duration <= 120:
        raise SystemExit(f"QA failed: narration duration {duration:.2f}s is outside 65–120s")

    scenes = job["scenes"]
    per_scene = duration / len(scenes)
    frame_paths = []
    for i, scene in enumerate(scenes):
        path = frames / f"scene_{i:02d}.png"
        render_scene(scene, job.get("title", "Paper Knowledge"), i, path)
        frame_paths.append(path)

    concat = work / "concat.txt"
    lines = []
    for p in frame_paths:
        lines.append(f"file '{p.resolve()}'")
        lines.append(f"duration {per_scene:.6f}")
    lines.append(f"file '{frame_paths[-1].resolve()}'")
    concat.write_text("\n".join(lines), encoding="utf-8")

    video = out / "paper_knowledge.mp4"
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-i", str(narration),
        "-vf", "fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-shortest", str(video)
    ])

    info = ffprobe(video)
    vstreams = [s for s in info["streams"] if s.get("codec_type") == "video"]
    astreams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    actual = float(info["format"]["duration"])
    if not vstreams or not astreams:
        raise SystemExit("QA failed: video or audio stream missing")
    v = vstreams[0]
    if (int(v["width"]), int(v["height"])) != (1080, 1920):
        raise SystemExit(f"QA failed: resolution is {v['width']}x{v['height']}")
    if not 65 <= actual <= 120:
        raise SystemExit(f"QA failed: final duration {actual:.2f}s is outside 65–120s")

    report = {
        "ok": True,
        "duration_seconds": round(actual, 3),
        "resolution": "1080x1920",
        "has_audio": True,
        "scenes": len(scenes),
        "voice": job.get("voice", "af_sky"),
    }
    (out / "qa.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python src/build_video.py jobs/current.json")
    main(sys.argv[1])
