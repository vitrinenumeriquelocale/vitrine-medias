import numpy as np, wave, sys
sr=44100; dur=float(sys.argv[1]); out=sys.argv[2]
n=int(sr*dur); t=np.arange(n)/sr; mix=np.zeros(n)
def note(f): return 440*2**((f-69)/12)
bpm=104; beat=60/bpm; step=beat/2
# low drone A1 + E2, slow tremolo
for m,a in [(33,.22),(40,.12)]:
    f=note(m); mix+=a*np.sin(2*np.pi*f*t)*(0.75+0.25*np.sin(2*np.pi*0.25*t))
# pizzicato ostinato in A minor
pat=[57,60,64,60,57,60,65,60, 57,60,64,60,56,59,64,59]
i=0; s=0.0
while s<dur:
    m=pat[i%len(pat)]; f=note(m); L=int(sr*0.45); st=int(s*sr)
    if st>=n: break
    tt=np.arange(min(L,n-st))/sr
    env=np.exp(-tt*9)
    tone=(np.sin(2*np.pi*f*tt)+0.35*np.sin(2*np.pi*2*f*tt)+0.12*np.sin(2*np.pi*3*f*tt))*env
    mix[st:st+len(tt)]+=0.16*tone
    s+=step; i+=1
# soft clock tick on each beat
rng=np.random.default_rng(1); s=0.0
while s<dur:
    st=int(s*sr); L=int(sr*0.03)
    if st+L<n:
        nz=rng.standard_normal(L)*np.exp(-np.arange(L)/sr*180)
        nz=np.diff(nz,prepend=0)
        mix[st:st+L]+=0.05*nz
    s+=beat
# fade in/out
fi=int(sr*0.8); fo=int(sr*1.5)
mix[:fi]*=np.linspace(0,1,fi); mix[-fo:]*=np.linspace(1,0,fo)
mix/=np.max(np.abs(mix))*1.05
st=np.stack([mix, np.roll(mix,int(sr*0.012))],1)
data=(st*32767).astype(np.int16)
w=wave.open(out,"wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(data.tobytes()); w.close()
print("ok")
