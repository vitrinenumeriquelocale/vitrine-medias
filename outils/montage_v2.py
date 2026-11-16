"""Nora montage v2: hard cuts, slow push-ins, punch zooms, grade + grain, whoosh SFX, music ducking.
Usage: python3 -I montage_v2.py <reel_dir> <audio_dir> <spec.json> <out.mp4>
spec.json: {"clips": [{"src": "p1.mp4", "kind": "nora|broll", "zoom": [z0, z1], "punch": t_or_null,
             "recrop": [t_from, x, y, w, h] or null, "blur": [x, y, w, h] or null}, ...], "hit": plan_index_or_null}"""
import json, subprocess, sys, os
R, A, SPEC, OUT = sys.argv[1:5]
spec = json.load(open(SPEC))
def dur(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout)
def run(args):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y"] + args, capture_output=True, text=True)
    if r.returncode: print(r.stderr); sys.exit(1)
GRADE = "eq=contrast=1.05:saturation=0.9:gamma=0.98,colorbalance=rs=0.03:gs=0.01:bs=-0.03:rm=0.02:bm=-0.02,vignette=PI/5,noise=alls=7:allf=t+u"
parts = []
for i, c in enumerate(spec["clips"]):
    n = i + 1; d = dur(f"{A}/seg{n}.wav"); src = f"{R}/{c['src']}"
    z0, z1 = c.get("zoom", [1.0, 1.06])
    base = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
    blurs = c.get("blurs") or ([c["blur"]] if c.get("blur") else [])
    for bi, (x, y, w, h) in enumerate(blurs):
        base += f",split[m{bi}][b{bi}];[b{bi}]crop={w}:{h}:{x}:{y},boxblur=16:2[bb{bi}];[m{bi}][bb{bi}]overlay={x}:{y}"
    # zoom expression (slow push, optional punch at time p to +18%)
    p = c.get("punch")
    zexpr = f"({z0}+({z1}-{z0})*t/{d:.3f})" + (f"*(1+0.18*min(1\\,max(0\\,(t-{p})/0.12)))" if p is not None else "")
    zoom = f"scale=w='trunc(1080*{zexpr}/2)*2':h='trunc(1920*{zexpr}/2)*2':eval=frame,crop=1080:1920"
    if c.get("recrop"):
        t0, x, y, w, h = c["recrop"]
        v = (f"[0:v]{base},split[a][b];[a]trim=0:{t0},setpts=PTS-STARTPTS,{zoom}[a1];"
             f"[b]trim={t0}:{d+1},setpts=PTS-STARTPTS,crop={w}:{h}:{x}:{y},scale=1080:1920,{zoom}[b1];[a1][b1]concat=n=2:v=1:a=0,{GRADE}[v]")
    else:
        v = f"[0:v]{base},tpad=stop_mode=clone:stop_duration=2,{zoom},{GRADE}[v]"
    loop = ["-stream_loop", "2"] if c["kind"] == "broll" else []
    if c.get("ss"): loop += ["-ss", str(c["ss"])]
    if c["kind"] == "broll" and c.get("slow"):
        v = v.replace("[0:v]", f"[0:v]setpts={c['slow']}*PTS,", 1)
    run(loop + ["-i", src, "-filter_complex", v, "-map", "[v]", "-t", f"{d:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", f"{R}/v{n}.mp4"])
    # optional cutaway inserted over a talking shot: "insert": {"src": "b2.mp4", "t0": 0.2, "t1": 2.4, "zoom": [1.0, 1.1], "blurs": [...]}
    ins = c.get("insert")
    if ins:
        t0, t1 = ins["t0"], min(ins["t1"], d); di = t1 - t0
        iz0, iz1 = ins.get("zoom", [1.0, 1.1])
        ib = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
        for bi, (x, y, w, h) in enumerate(ins.get("blurs", [])):
            ib += f",split[m{bi}][b{bi}];[b{bi}]crop={w}:{h}:{x}:{y},boxblur=16:2[bb{bi}];[m{bi}][bb{bi}]overlay={x}:{y}"
        iexpr = f"({iz0}+({iz1}-{iz0})*t/{di:.3f})"
        izoom = f"scale=w='trunc(1080*{iexpr}/2)*2':h='trunc(1920*{iexpr}/2)*2':eval=frame,crop=1080:1920"
        run(["-stream_loop", "2", "-i", f"{R}/{ins['src']}", "-filter_complex", f"[0:v]{ib},{izoom},{GRADE}[v]", "-map", "[v]", "-t", f"{di:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", f"{R}/i{n}.mp4"])
        segs = []
        if t0 > 0.02: segs.append(f"[0:v]trim=0:{t0:.3f},setpts=PTS-STARTPTS[p0]")
        segs.append("[1:v]setpts=PTS-STARTPTS[p1]")
        if d - t1 > 0.02: segs.append(f"[0:v]trim={t1:.3f}:{d:.3f},setpts=PTS-STARTPTS[p2]")
        labs = "".join(l for l, ok in (("[p0]", t0 > 0.02), ("[p1]", True), ("[p2]", d - t1 > 0.02)) if ok)
        segs.append(f"{labs}concat=n={labs.count('[')}:v=1:a=0[v]")
        run(["-i", f"{R}/v{n}.mp4", "-i", f"{R}/i{n}.mp4", "-filter_complex", ";".join(segs), "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", f"{R}/vi{n}.mp4"])
        os.replace(f"{R}/vi{n}.mp4", f"{R}/v{n}.mp4")
    parts.append((f"{R}/v{n}.mp4", d))
# concat video (hard cuts)
with open(f"{R}/list.txt", "w") as f:
    for pth, _ in parts: f.write(f"file '{pth}'\n")
run(["-f", "concat", "-safe", "0", "-i", f"{R}/list.txt", "-c", "copy", f"{R}/vcat.mp4"])
# voice concat
ins = []; [ins.extend(["-i", f"{A}/seg{k+1}.wav"]) for k in range(len(parts))]
run(ins + ["-filter_complex", "".join(f"[{k}:a]" for k in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[a]", "-map", "[a]", f"{R}/voice.wav"])
T = sum(d for _, d in parts)
# SFX: synthetic whoosh at each cut, low hit on spec['hit']
run(["-f", "lavfi", "-i", "anoisesrc=color=pink:duration=0.45:amplitude=0.6", "-af",
     "highpass=f=300,lowpass=f=6000,afade=t=in:d=0.25:curve=exp,afade=t=out:st=0.25:d=0.2,volume=0.35", f"{R}/whoosh.wav"])
run(["-f", "lavfi", "-i", "sine=frequency=48:duration=0.9", "-af", "afade=t=out:d=0.9:curve=exp,volume=0.9", f"{R}/hit.wav"])
cuts = []; acc = 0
for k2, (_, d) in enumerate(parts):
    ins = spec["clips"][k2].get("insert")
    if ins:
        if ins["t0"] > 0.35: cuts.append(acc + ins["t0"])
        if d - ins["t1"] > 0.02: cuts.append(acc + ins["t1"])
    acc += d
    if k2 < len(parts) - 1: cuts.append(acc)
sfx_in = []; filt = []; k = 0
for t in cuts:
    sfx_in += ["-i", f"{R}/whoosh.wav"]; filt.append(f"[{k}:a]adelay={int((t-0.3)*1000)}|{int((t-0.3)*1000)}[s{k}]"); k += 1
if spec.get("hit") is not None:
    t = sum(d for _, d in parts[:spec["hit"]])
    sfx_in += ["-i", f"{R}/hit.wav"]; filt.append(f"[{k}:a]adelay={int(t*1000)}|{int(t*1000)}[s{k}]"); k += 1
filt.append("".join(f"[s{j}]" for j in range(k)) + f"amix=inputs={k}:normalize=0,apad=whole_dur={T:.3f}[sfx]")
run(sfx_in + ["-filter_complex", ";".join(filt), "-map", "[sfx]", "-ac", "2", f"{R}/sfx.wav"])
music = spec.get("music", f"{R}/music.wav")
run(["-i", f"{R}/vcat.mp4", "-i", f"{R}/voice.wav", "-i", music, "-i", f"{R}/sfx.wav", "-filter_complex",
     f"[2:a]atrim=0:{T:.3f},volume={spec.get('music_vol', 0.22)},afade=t=in:d=0.4,afade=t=out:st={T-1.2:.3f}:d=1.2[m];"
     f"[1:a]asplit[v1][v2];[m][v2]sidechaincompress=threshold=0.05:ratio=6:attack=20:release=300[md];"
     f"[v1][md][3:a]amix=inputs=3:normalize=0,loudnorm=I=-14:TP=-1.5[a];"
     f"[0:v]subtitles={R}/subs.ass:fontsdir=/usr/share/fonts/truetype/google-fonts[v]",
     "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", OUT])
print(f"ok {T:.2f}s")
