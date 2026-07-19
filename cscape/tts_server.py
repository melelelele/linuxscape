import hashlib
import pathlib
from urllib.parse import quote

import edge_tts
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn


CACHE_DIR = pathlib.Path("generated_sounds")
CACHE_DIR.mkdir(exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def cache_filename(text: str, voice: str, rate: str, pitch: str) -> pathlib.Path:
    key = f"{voice}|{rate}|{pitch}|{text}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.mp3"


@app.get("/tts")
async def tts(
    text: str = Query(..., min_length=1, max_length=2000),
    voice: str = Query("de-DE-KatjaNeural"),
    rate: str = Query("+0%"),
    pitch: str = Query("+0Hz"),
):
    try:
        path = cache_filename(text, voice, rate, pitch)

        if not path.exists():
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=rate,
                pitch=pitch,
            )
            await communicate.save(str(path))

        safe_name = quote("scene.mp3")

        return FileResponse(
            path,
            media_type="audio/mpeg",
            filename=safe_name,
        )

    except Exception as error:
        return JSONResponse(
            status_code=500,
            content={"error": str(error)},
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765)
