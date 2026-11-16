"""Syllable-nucleus aligner + ASS writer for Nora Reels (hard cuts, no crossfade).
Usage: python3 -I align_subs.py <plans.json> <audio_dir> <out.ass>
plans.json: {"hook": "...", "end": "...", "plans": [[chunk, ...], ...]} where chunk text marks keywords with *...*
Audio: <audio_dir>/seg1.wav ... segN.wav (final processed per-plan voice)."""
import json, re, subprocess, sys
import numpy as np
spec = json.load(open(sys.argv[1])); AD = sys.argv[2]; OUT = sys.argv[3]
NUM = spec.get("num", {})
def syl(t):
    t = t.lower().replace("*", "")
    for k, v in NUM.items(): t = t.replace(k.lower(), v)
    t = re.sub(r"e\b", "", t)
    return max(1, len(re.findall(r"[aeiouyéèêàâîïôûùœ]+", t)))
def load(f):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", f, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(float) / 32768
def nuclei(a):
    hop = 160; n = len(a) // hop
    e = np.array([np.sqrt(np.mean(a[i*hop:(i+1)*hop]**2)) for i in range(n)])
    k = np.ones(5) / 5; e = np.convolve(e, k, "same")
    thr = max(0.02, 0.25 * np.percentile(e, 95))
    peaks = []
    for i in range(2, n - 2):
        if e[i] > thr and e[i] == e[max(0, i-6):i+7].max():
            if not peaks or i - peaks[-1] >= 9: peaks.append(i)
    return [p * hop / 16000 for p in peaks], len(a) / 16000
def ts(t): return f"{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}"
def fmt(x): return re.sub(r"\*(.+?)\*", r"{\\c&H00D3FF&}\1{\\c&HFFFFFF&}", x)
HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Poppins,112,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,5,90,90,0,1
Style: Hook,Poppins,96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,3,18,0,8,70,70,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
lines, off, durs = [], 0.0, []
for i, chunks in enumerate(spec["plans"]):
    a = load(f"{AD}/seg{i+1}.wav"); peaks, dur = nuclei(a); durs.append(dur)
    w = [syl(c) for c in chunks]; T = sum(w)
    def at(sidx):
        if not peaks: return dur * sidx / T
        j = sidx * len(peaks) / T
        lo = int(min(len(peaks) - 1, j))
        return max(0, peaks[lo] - 0.07)
    acc = 0
    starts = []
    for c in chunks: starts.append(at(acc)); acc += syl(c)
    for j, c in enumerate(chunks):
        st = starts[j]; en = starts[j+1] if j + 1 < len(chunks) else min(dur, (peaks[-1] + 0.35) if peaks else dur)
        if en - st < 0.25: en = st + 0.25
        lines.append(f"Dialogue: 0,{ts(off+st)},{ts(off+en)},Cap,,0,0,0,,{{\\pos(540,1100)\\fscx70\\fscy70\\t(0,80,\\fscx104\\fscy104)\\t(80,140,\\fscx100\\fscy100)}}" + fmt(c))
    off += dur
total = off
lines.append(f"Dialogue: 1,{ts(0)},{ts(2.0)},Hook,,0,0,0,,{{\\pos(540,290)\\fad(0,150)}}" + spec["hook"])
lines.append(f"Dialogue: 1,{ts(total-1.8)},{ts(total)},Hook,,0,0,0,,{{\\pos(540,290)\\fad(150,0)}}" + spec["end"])
open(OUT, "w").write(HEAD + "\n".join(lines) + "\n")
print(" ".join(f"{d:.3f}" for d in durs), f"total={total:.2f}")
