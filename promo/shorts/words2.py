import subprocess, sys, numpy as np
from faster_whisper import WhisperModel
src,a,b=sys.argv[1],float(sys.argv[2]),float(sys.argv[3])
raw=subprocess.run(["ffmpeg","-v","error","-ss",str(a),"-t",str(b-a),"-i",src,"-vn","-ac","1","-ar","16000","-f","f32le","-"],capture_output=True,check=True).stdout
m=WhisperModel("small",device="cpu",compute_type="int8")
segs,_=m.transcribe(np.frombuffer(raw,np.float32),language="ru",word_timestamps=True,vad_filter=False)
with open(sys.argv[4],"w",encoding="utf-8") as f:
    f.write(" ".join(f"{a+w.start:.1f}:{w.word.strip()}" for s in segs for w in s.words))
