from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import subprocess
import json
from pydantic import BaseModel

app = FastAPI(title="Airdown Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoURL(BaseModel):
    url: str

@app.get("/health")
def health():
    return {"status": "ok", "message": "Airdown Python backend is running 🚀"}

@app.post("/info")
def get_info(data: VideoURL):
    url = data.url.strip()
    if not url or ("youtube.com" not in url and "youtu.be" not in url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    try:
        command = [
            "yt-dlp", "--dump-json", "--no-warnings",
            "--extractor-args", "youtube:player_client=web,android,ios,web_embed",
            "--user-agent", "Mozilla/5.0",
            url
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            raise Exception(result.stderr or "yt-dlp failed")

        info = json.loads(result.stdout)

        formats = []
        for f in info.get("formats", []):
            if f.get("vcodec") != "none" and f.get("acodec") != "none":
                quality = f"{f.get('height')}p" if f.get('height') else f.get("format_note", "Unknown")
                size = round(f.get("filesize_approx", 0) / (1024*1024)) if f.get("filesize_approx") else "Unknown"
                formats.append({
                    "format_id": f["format_id"],
                    "quality": quality,
                    "ext": f.get("ext", "mp4"),
                    "filesize": f"{size} MB" if size != "Unknown" else "Unknown"
                })

        # Sort by quality
        formats.sort(key=lambda x: int(x["quality"].replace("p", "")) if "p" in x["quality"] else 0, reverse=True)

        formats.insert(0, {
            "format_id": "bestaudio",
            "quality": "Audio Only (MP3)",
            "ext": "mp3",
            "filesize": "Varies"
        })

        return {
            "title": info.get("title", "Unknown"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration_string", "Unknown"),
            "formats": formats[:15]
        }

    except Exception as e:
        print("Error:", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch video. Try a different public video or try again later.")

@app.get("/download")
def download(url: str, format_id: str):
    try:
        if format_id == "bestaudio":
            cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "--no-warnings", "-o", "-", url]
            media_type = "audio/mpeg"
            filename = "Airdown_Audio.mp3"
        else:
            cmd = ["yt-dlp", "-f", f"{format_id}+bestaudio/best", "--merge-output-format", "mp4", "--no-warnings", "-o", "-", url]
            media_type = "video/mp4"
            filename = "Airdown_Video.mp4"

        def generate():
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for chunk in iter(lambda: process.stdout.read(8192), b""):
                yield chunk

        return StreamingResponse(generate(), media_type=media_type, headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail="Download failed")
