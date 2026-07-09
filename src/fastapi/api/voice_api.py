from fastapi import APIRouter, Request
from pydantic import BaseModel
from src.audio_util.make_voice_google import make_voice_google
from src.audio_util.make_voice_openai import make_voice_openai


class VoiceRequest(BaseModel):
    vendor: str = "google-tts" #openai   
    text: str
    voice: str = "alloy"  # Default voice is set to "alloy"
    instructions: str #openai 일때만


class VoiceResponse(BaseModel):
    success: bool
    voice_path: str

router = APIRouter(
    prefix="/generate",
    tags=["Voice"]
)

# fastapi_domain="http://127.0.0.1:8000"
down_path = "download"
static_root_dir = "output"

# app.mount(f"/{down_path}", StaticFiles(directory=static_root_dir), name=down_path)

@router.post("/voice", response_model=VoiceResponse)
async def create_voice(request: Request, body: VoiceRequest):

    if body.vendor == "openai" :

        res = make_voice_openai(
            text=body.text,
            instructions=body.instructions,
            voice=body.voice
        )
    elif body.vendor == "google-tts" :
        res = make_voice_google(text=body.text, model_name=body.voice)

    #voice_path = res[0]
    #print("res[0] : " + res[0]);
    
    # return_url = fastapi_domain + app.url_path_for(down_path, path= res[1].replace(static_root_dir, ""))

    base_url = str(request.base_url).rstrip("/")
    relative = res[1].replace(static_root_dir, "").replace("\\", "/")
    return_url = f"{base_url}/{down_path}{relative}"

    print("return_url : " + return_url);

    return VoiceResponse(
        success=True,
        voice_path=return_url
    )