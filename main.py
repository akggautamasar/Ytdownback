from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import subprocess
import json
from pydantic import BaseModel

app = FastAPI(title="Airdown")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoURL(BaseModel):
    url: str

@app.get("/health")
def health():
    return {"status": "ok", "message": "Airdown backend is running 🚀"}

@app.post("/info")
def get_info(data: VideoURL):
    url = data.url.strip()
    if not url or ("youtube.com" not in url and "youtu.be" not in url):
        raise HTTPException(400, "Invalid YouTube URL")

    try:
        cmd = [
            "yt-dlp", "--dump-json", "--no-warnings",
            "--extractor-args", "youtube:player_client=web,android,ios",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        
        if result.returncode != 0:
            raise Exception(result.stderr)

        info = json.loads(result.stdout)

        formats = []
        for f in info.get("formats", []):
            if f.get("vcodec") != "none" and f.get("acodec") != "none":
                quality = f"{f.get('height')}p" if f.get('height') else f.get("format_note", "Unknown")
                size = round(f.get("filesize_approx", 0) / (1024 * 1024)) if f.get("filesize_approx") else "Unknown"
                formats.append({
                    "format_id": f.get("format_id"),
                    "quality": quality,
                    "ext": f.get("ext", "mp4"),
                    "filesize": f"{size} MB" if size != "Unknown" else "Unknown"
                })

        formats.sort(key=lambda x: int(x["quality"].replace("p", "")) if "p" in x["quality"] else 0, reverse=True)

        formats.insert(0, {"format_id": "bestaudio", "quality": "Audio Only (MP3)", "ext": "mp3", "filesize": "Varies"})

        return {
            "title": info.get("title", "Unknown"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration_string", "Unknown"),
            "formats": formats[:12]
        }

    except Exception as e:
        print("Error:", str(e))
        raise HTTPException(500, "Failed to fetch video. Try a different public video.")

@app.get("/download")
def download_video(url: str, format_id: str):
    try:
        if format_id == "bestaudio":
            cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "-o", "-", url]
            media_type = "audio/mpeg"
            filename = "Airdown_Audio.mp3"
        else:
            cmd = ["yt-dlp", "-f", f"{format_id}+bestaudio/best", "--merge-output-format", "mp4", "-o", "-", url]
            media_type = "video/mp4"
            filename = "Airdown_Video.mp4"

        def stream():
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            for chunk in iter(lambda: process.stdout.read(64*1024), b""):
                yield chunk

        return StreamingResponse(stream(), media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    except Exception:
        raise HTTPException(500, "Download failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
