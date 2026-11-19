import subprocess, os, sys
W = sys.argv[1]
os.chdir(W)
os.makedirs("clips", exist_ok=True)
O = 2.5          # narration offset (intro)
END_PAD = 3.0
NARR = 43.15
XF = 0.7         # crossfade
FPS = 30

# (image, narration start, narration end, motion)
scenes = [
    ("01", -O,    7.6,  "in"),
    ("02", 7.6,   11.2, "in_slow"),
    ("03", 11.2,  15.4, "pan_r"),
    ("11", 15.4,  17.6, "pan_l"),
    ("04", 17.6,  19.95, "in"),
    ("05", 19.95, 22.05, "up"),
    ("12", 22.05, 24.95, "pan_r"),
    ("07", 24.95, 27.8, "in"),
    ("08", 27.8,  30.65, "pan_l"),
    ("09", 30.65, 37.45, "in_slow"),
    ("10", 37.45, NARR + END_PAD, "out"),
]

def motion(kind, n):
    # zoompan expressions; source upscaled to 3840x2160
    p = f"(on/{n})"
    if kind == "in":      z, x, y = f"1.0+0.12*{p}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif kind == "in_slow": z, x, y = f"1.0+0.07*{p}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif kind == "out":   z, x, y = f"1.15-0.13*{p}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif kind == "pan_r": z, x, y = "1.12", f"(iw-iw/zoom)*{p}", "ih/2-(ih/zoom/2)"
    elif kind == "pan_l": z, x, y = "1.12", f"(iw-iw/zoom)*(1-{p})", "ih/2-(ih/zoom/2)"
    elif kind == "up":    z, x, y = "1.12", "iw/2-(iw/zoom/2)", f"(ih-ih/zoom)*(1-{p})"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s=1920x1080:fps={FPS}"

durs = []
for i, (img, s, e, kind) in enumerate(scenes):
    d = (e - s) + (XF if i < len(scenes) - 1 else 0)
    durs.append(d)
    n = int(round(d * FPS))
    vf = (f"scale=3840:2160:flags=lanczos,{motion(kind, n)},"
          f"eq=saturation=1.05,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS),
                    "-i", f"img/{img}.png", "-vf", vf, "-frames:v", str(n),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", f"clips/{i:02d}.mp4"],
                   check=True)
    print("clip", i, img, round(d, 2), flush=True)

# xfade chain
inputs, chain, last, off = [], [], "0:v", 0.0
for i in range(len(scenes)):
    inputs += ["-i", f"clips/{i:02d}.mp4"]
for i in range(1, len(scenes)):
    off += durs[i - 1] - XF
    out = f"v{i}"
    chain.append(f"[{last}][{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[{out}]")
    last = out
total = O + NARR + END_PAD
fc = ";".join(chain) + f";[{last}]fade=t=in:st=0:d=1,fade=t=out:st={total-1.5:.2f}:d=1.5,ass=subs.ass[vout]"
subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc,
                "-map", "[vout]", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", "video_only.mp4"], check=True)

# audio: narration + soft wind + low drone
afc = (f"[0:a]adelay={int(O*1000)}|{int(O*1000)},apad,atrim=0:{total},volume=1.6[nar];"
       f"anoisesrc=c=brown:a=0.5:d={total},lowpass=f=400,highpass=f=60,"
       f"volume='0.10+0.05*sin(t*0.6)':eval=frame,aformat=channel_layouts=stereo[wind];"
       f"sine=f=110:d={total},volume=0.035[d1];sine=f=164.8:d={total},volume=0.02[d2];"
       f"sine=f=220:d={total},volume=0.012[d3];"
       f"[d1][d2][d3]amix=inputs=3:normalize=0,tremolo=f=0.15:d=0.4,aformat=channel_layouts=stereo[drone];"
       f"[wind][drone]amix=inputs=2:normalize=0,afade=t=in:d=2,afade=t=out:st={total-3:.2f}:d=3[bg];"
       f"[nar][bg]amix=inputs=2:normalize=0,alimiter=limit=0.95[aout]")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "narration.mp3", "-filter_complex", afc,
                "-map", "[aout]", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "audio.m4a"], check=True)

subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "video_only.mp4", "-i", "audio.m4a",
                "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart",
                "Asan_Qaigy_Zheruiyq.mp4"], check=True)
print("done", total)
