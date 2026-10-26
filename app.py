"""
Voice Studio - website
    pip install -r requirements.txt
    python app.py   ->  http://localhost:5000
"""
import tempfile
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request, send_from_directory

import pipeline as pl

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024
ROOT = Path(tempfile.gettempdir()) / "voice_studio"
ROOT.mkdir(exist_ok=True)
JOBS = {}

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voice Studio - Studio-quality voice from any recording</title>
<style>
:root{--acc:#7c8cff;--mut:#a9a9c4;--glass:rgba(255,255,255,.08);--line:rgba(255,255,255,.16)}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;font-family:-apple-system,system-ui,Segoe UI,sans-serif;color:#f4f4fb;min-height:100vh;
background:radial-gradient(circle at 15% 5%,#3b2a7a,transparent 45%),radial-gradient(circle at 90% 40%,#14406b,transparent 45%),#0d0f22}
.wrap{max-width:880px;margin:0 auto;padding:0 20px}
nav{display:flex;justify-content:space-between;align-items:center;padding:20px 0}
nav b{font-size:18px}nav a{color:var(--mut);text-decoration:none;font-size:14px}
.hero{text-align:center;padding:48px 0 32px}
.hero h1{font-size:clamp(32px,6vw,54px);line-height:1.08;margin:0 0 14px}
.hero h1 span{background:linear-gradient(90deg,#9aa6ff,#6ee7ff);-webkit-background-clip:text;background-clip:text;color:transparent}
.hero p{color:var(--mut);font-size:17px;max-width:560px;margin:0 auto 24px}
.btn{display:inline-block;padding:14px 26px;border-radius:16px;background:var(--acc);color:#fff;font-weight:600;text-decoration:none;border:0;font-size:16px;cursor:pointer}
.feat{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:36px 0}
.glass{background:var(--glass);border:1px solid var(--line);border-radius:24px;backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px)}
.feat div{padding:20px}.feat h3{margin:0 0 6px;font-size:16px}.feat p{margin:0;color:var(--mut);font-size:14px}
#tool{padding:26px;margin:20px 0 48px;box-shadow:0 20px 60px rgba(0,0,0,.35)}
#tool h2{margin:0 0 16px}
.drop{border:2px dashed rgba(255,255,255,.28);border-radius:18px;padding:30px 14px;text-align:center;cursor:pointer;transition:.2s}
.drop.over{border-color:var(--acc);background:rgba(124,140,255,.12)}
.drop b{display:block}.drop span{color:var(--mut);font-size:13px}
.opt{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid var(--line);font-size:15px}
.opt small{display:block;color:var(--mut);font-size:12.5px;margin-top:2px}
.opt.static{opacity:.85}
input[type=checkbox]{flex:none;width:46px;height:27px;appearance:none;-webkit-appearance:none;background:rgba(255,255,255,.2);border-radius:14px;position:relative;cursor:pointer;transition:.2s}
input[type=checkbox]::after{content:"";position:absolute;top:3px;left:3px;width:21px;height:21px;border-radius:50%;background:#fff;transition:.2s}
input[type=checkbox]:checked{background:var(--acc)}input[type=checkbox]:checked::after{left:22px}
#iso{display:none;padding:14px 0}
#iso .drop{padding:18px}
input[type=range]{width:100%;accent-color:var(--acc)}
.rl{display:flex;justify-content:space-between;font-size:12px;color:var(--mut)}
#go{width:100%;margin-top:18px}#go:disabled{opacity:.5;cursor:not-allowed}
#status{margin-top:14px;text-align:center;color:var(--mut);font-size:14px;min-height:20px}
.bar{height:6px;border-radius:3px;background:rgba(255,255,255,.12);overflow:hidden;margin-top:10px;display:none}
.bar i{display:block;height:100%;width:40%;background:var(--acc);border-radius:3px;animation:s 1.2s infinite ease-in-out}
@keyframes s{0%{margin-left:-40%}100%{margin-left:100%}}
#result{display:none;margin-top:18px}
.cmp{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:600px){.cmp{grid-template-columns:1fr}}
.cmp h4{margin:0 0 6px;font-size:13px;color:var(--mut);font-weight:500}
audio,video{width:100%;border-radius:12px}
a.dl{display:block;text-align:center;margin-top:14px;padding:13px;border-radius:14px;background:rgba(255,255,255,.14);color:#fff;font-weight:600;text-decoration:none}
.note{font-size:12.5px;color:var(--mut);margin-top:10px}
footer{text-align:center;color:var(--mut);font-size:13px;padding:24px 0 40px}
</style></head><body>
<div class="wrap">
<nav><b>Voice Studio</b><a href="#tool">Try it</a></nav>
<section class="hero">
<h1>Studio-quality voice,<br><span>from any recording</span></h1>
<p>Remove background noise, cut out other people talking behind you, and make your voice sound like it was recorded in a studio.</p>
<a class="btn" href="#tool">Enhance a file</a>
</section>
<section class="feat">
<div class="glass"><h3>Noise removal</h3><p>Fans, traffic, hum and room noise gone.</p></div>
<div class="glass"><h3>Remove other voices</h3><p>Give a short sample of your voice and others are faded out.</p></div>
<div class="glass"><h3>AI enhance</h3><p>Restores clarity and warmth, Adobe Podcast style.</p></div>
<div class="glass"><h3>Audio and video</h3><p>Upload an mp4; the picture stays untouched.</p></div>
</section>

<section id="tool" class="glass">
<h2>Enhance your voice</h2>
<div class="drop" id="drop"><b id="fname">Tap or drop your recording</b><span>mp4, mov, mkv, wav, mp3, m4a</span></div>
<input id="file" type="file" accept="audio/*,video/*" hidden>

<div class="opt static"><div>Remove background noise<small>Always on</small></div><span>On</span></div>
<div class="opt"><div>AI voice enhance<small>Studio-like clarity. Slower; much faster with a GPU</small></div><input id="enh" type="checkbox" checked></div>
<div class="opt"><div>Remove other people's voices<small>Needs a 10-30 s clean sample of your voice</small></div><input id="isoOn" type="checkbox"></div>
<div id="iso">
  <div class="drop" id="drop2"><b id="fname2">Add a sample of your voice</b><span>Any clip of only you speaking</span></div>
  <input id="sample" type="file" accept="audio/*,video/*" hidden>
  <div style="margin-top:14px"><div class="rl"><span>Gentle</span><span>Strict</span></div>
  <input id="thr" type="range" min="20" max="65" value="40"></div>
</div>
<div class="opt"><div>Loudness (LUFS)<small>YouTube = -14</small></div><input id="lufs" type="number" value="-14" style="width:72px;padding:8px;border-radius:10px;border:1px solid var(--line);background:rgba(255,255,255,.1);color:#fff;text-align:center"></div>

<button class="btn" id="go" disabled>Enhance</button>
<div class="bar" id="bar"><i></i></div>
<div id="status"></div>
<div id="result"></div>
</section>
<footer>Voice Studio. Files are processed on this server and not shared.</footer>
</div>

<script>
const $=id=>document.getElementById(id);let file=null,sample=null;
function wireDrop(dropId,inpId,nameId,cb){
  const d=$(dropId),i=$(inpId);
  d.onclick=()=>i.click();i.onchange=()=>i.files[0]&&set(i.files[0]);
  d.ondragover=e=>{e.preventDefault();d.classList.add('over')};
  d.ondragleave=()=>d.classList.remove('over');
  d.ondrop=e=>{e.preventDefault();d.classList.remove('over');e.dataTransfer.files[0]&&set(e.dataTransfer.files[0])};
  function set(f){$(nameId).textContent=f.name;cb(f)}
}
function refresh(){$('go').disabled=!file||($('isoOn').checked&&!sample)}
wireDrop('drop','file','fname',f=>{file=f;refresh()});
wireDrop('drop2','sample','fname2',f=>{sample=f;refresh()});
$('isoOn').onchange=()=>{$('iso').style.display=$('isoOn').checked?'block':'none';refresh()};

$('go').onclick=async()=>{
  const fd=new FormData();
  fd.append('file',file);if($('isoOn').checked)fd.append('sample',sample);
  fd.append('enhance',$('enh').checked?'1':'');
  fd.append('lufs',$('lufs').value);
  fd.append('threshold',($('thr').value/100).toString());
  $('go').disabled=true;$('result').style.display='none';$('bar').style.display='block';
  $('status').textContent='Uploading...';
  try{
    const r=await fetch('/process',{method:'POST',body:fd});const j=await r.json();
    if(!r.ok)throw new Error(j.error||'Upload failed');
    while(true){
      await new Promise(s=>setTimeout(s,2000));
      const s=await (await fetch('/status/'+j.id)).json();
      if(s.error)throw new Error(s.error);
      $('status').textContent=s.status;
      if(s.done){show(s);break}
    }
  }catch(e){$('status').textContent='Error: '+e.message}
  $('bar').style.display='none';refresh();
};
function show(s){
  const vid=/\.(mp4|mov|mkv|webm|m4v|avi)$/i.test(s.name);
  const tag=u=>vid?`<video controls src="${u}"></video>`:`<audio controls src="${u}"></audio>`;
  $('result').innerHTML=`<div class="cmp"><div><h4>Before</h4>${tag(s.original)}</div><div><h4>After</h4>${tag(s.url)}</div></div>
  <a class="dl" href="${s.url}" download="${s.name}">Download</a>
  ${s.isolated?'<p class="note">If your voice got cut, move the slider toward Gentle and run again. If other voices remain, move it toward Strict.</p>':''}`;
  $('result').style.display='block';$('status').textContent='Done.';
}
</script></body></html>"""


def worker(job_id, d, src, sample, enhance, lufs, threshold):
    j = JOBS[job_id]
    is_video = src.suffix.lower() in pl.VIDEO_EXT
    try:
        raw, clean, final = d / "raw.wav", d / "clean.wav", d / "final.wav"
        j["status"] = "Extracting audio..."
        pl.extract_audio(src, raw)

        j["status"] = "Removing background noise..."
        pl.denoise(raw, clean)

        if sample:
            j["status"] = "Removing other voices..."
            iso = d / "iso.wav"
            pl.isolate_voice(clean, sample, iso, threshold)
            clean = iso

        if enhance:
            j["status"] = "AI voice enhancement (this is the slow step)..."
            enh = d / "enh.wav"
            pl.ai_enhance(clean, enh, d)
            clean = enh

        j["status"] = "Polishing and saving..."
        pl.polish(clean, final, lufs)

        out_name = f"{j['stem']}_enhanced{src.suffix if is_video else '.wav'}"
        out = d / out_name
        if is_video:
            pl.merge_video(src, final, out)
        else:
            pl.run(["ffmpeg", "-y", "-i", final, out])

        j.update(done=True, status="Done", name=out_name,
                 url=f"/files/{job_id}/{out_name}",
                 original=f"/files/{job_id}/{src.name}",
                 isolated=bool(sample))
    except Exception as e:
        j["error"] = str(e)[:400]


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.post("/process")
def process():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="No file uploaded"), 400
    job_id = uuid.uuid4().hex[:10]
    d = ROOT / job_id
    d.mkdir()

    ext = Path(f.filename).suffix.lower() or ".wav"
    src = d / f"original{ext}"
    f.save(src)

    sample = None
    s = request.files.get("sample")
    if s and s.filename:
        sample = d / f"sample{Path(s.filename).suffix.lower() or '.wav'}"
        s.save(sample)

    try:
        lufs = float(request.form.get("lufs", -14))
        threshold = float(request.form.get("threshold", 0.4))
    except ValueError:
        lufs, threshold = -14.0, 0.4

    JOBS[job_id] = {"status": "Queued...", "stem": Path(f.filename).stem}
    threading.Thread(
        target=worker,
        args=(job_id, d, src, sample, bool(request.form.get("enhance")), lufs, threshold),
        daemon=True,
    ).start()
    return jsonify(id=job_id)


@app.get("/status/<job_id>")
def status(job_id):
    return jsonify(JOBS.get(job_id, {"error": "Unknown job"}))


@app.get("/files/<job_id>/<path:name>")
def files(job_id, name):
    return send_from_directory(ROOT / job_id, name)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
