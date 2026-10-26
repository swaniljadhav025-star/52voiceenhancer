"""Voice Studio pipeline: denoise -> isolate my voice -> AI enhance -> polish."""
import subprocess
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
SR = 48000


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr[-800:]}")


def extract_audio(src, out):
    """Any audio/video -> 48 kHz mono WAV."""
    run(["ffmpeg", "-y", "-i", src, "-vn", "-ac", "1", "-ar", SR, out])


def denoise(src, out):
    """Remove background noise (DeepFilterNet)."""
    import soundfile as sf
    import torch
    from df.enhance import enhance, init_df

    model, df_state, _ = init_df()
    data, sr = sf.read(str(src), dtype="float32")
    audio = torch.from_numpy(data).unsqueeze(0)
    cleaned = enhance(model, df_state, audio)
    sf.write(str(out), cleaned.squeeze(0).numpy(), df_state.sr())


def isolate_voice(src, sample, out, threshold=0.4):
    """
    Keep only the person who sounds like `sample`; fade out other voices.
    Uses speaker embeddings (SpeechBrain ECAPA) on sliding windows.
    Limitation: if two people talk at the same moment, that moment is kept or cut as a whole.
    """
    import numpy as np
    import soundfile as sf
    import torch
    import torchaudio
    from scipy.ndimage import median_filter
    from speechbrain.inference.speaker import EncoderClassifier

    clf = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(Path.home() / ".cache" / "ecapa"),
    )

    def load(path, target_sr):
        d, sr = sf.read(str(path), dtype="float32")
        if d.ndim > 1:
            d = d.mean(axis=1)
        w = torch.from_numpy(d).unsqueeze(0)
        if sr != target_sr:
            w = torchaudio.functional.resample(w, sr, target_sr)
        return w

    def embed(batch):  # (B, T) -> (B, 192), L2-normalised
        e = clf.encode_batch(batch).squeeze(1)
        return torch.nn.functional.normalize(e, dim=-1)

    ref = embed(load(sample, 16000))[0]

    w16 = load(src, 16000)[0]
    n = w16.shape[0]
    win, hop = 24000, 8000  # 1.5 s window, 0.5 s hop
    if n < win:
        w16 = torch.nn.functional.pad(w16, (0, win - n))
        n = win
    starts = list(range(0, n - win + 1, hop))
    segs = torch.stack([w16[s:s + win] for s in starts])

    sims = []
    with torch.no_grad():
        for i in range(0, len(segs), 32):
            sims += (embed(segs[i:i + 32]) @ ref).tolist()

    keep = (np.array(sims) >= threshold).astype(float)
    keep = median_filter(keep, size=3, mode="nearest")  # drop 1-window flicker

    audio, sr = sf.read(str(src), dtype="float32")
    centers = (np.array(starts) + win / 2) / 16000 * sr
    mask = np.interp(np.arange(len(audio)), centers, keep)
    # smooth the on/off edges (~120 ms) so cuts do not click
    k = np.hanning(int(sr * 0.12)); k /= k.sum()
    mask = np.convolve(mask, k, mode="same")
    sf.write(str(out), (audio * mask).astype("float32"), sr)


def ai_enhance(src, out, workdir):
    """Studio-style generative enhancement (Resemble Enhance)."""
    import torch

    workdir = Path(workdir)
    in_dir, out_dir = workdir / "re_in", workdir / "re_out"
    in_dir.mkdir(exist_ok=True)
    out_dir.mkdir(exist_ok=True)
    (in_dir / "a.wav").write_bytes(Path(src).read_bytes())
    device = "cuda" if torch.cuda.is_available() else "cpu"
    run(["resemble-enhance", in_dir, out_dir, "--device", device])
    run(["ffmpeg", "-y", "-i", out_dir / "a.wav", "-ar", SR, "-ac", 1, out])


def polish(src, out, lufs=-14.0):
    chain = (
        "highpass=f=80,"
        "equalizer=f=3000:t=q:w=1:g=2,"
        "acompressor=threshold=-18dB:ratio=3:attack=10:release=150,"
        f"loudnorm=I={lufs}:TP=-1.5:LRA=11"
    )
    run(["ffmpeg", "-y", "-i", src, "-af", chain, "-ar", SR, out])


def merge_video(video, audio, out):
    run(["ffmpeg", "-y", "-i", video, "-i", audio,
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", out])
