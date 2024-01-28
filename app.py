import os
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, Header, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from openai import OpenAI, api_key
from uuid import uuid4
from elevenlabs import clone, generate, set_api_key, voices

# Basic Setup
load_dotenv()
set_api_key(api_key=os.getenv('ELEVENLABS_API_KEY'))

app = FastAPI()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

@app.get('/')
async def index():
    """Index Page for API server"""
    return JSONResponse(status_code=200, content={'status': 'success', 'message': 'Welcome to VirtuConnect API Server'})

@app.post('/api/voice_training')
async def add_voice_to_elevenlabs(
    user_id: str = Header(),
    voice_files: list[UploadFile] = File(...)
):
    """Add voice to ElevenLabs"""
    # Get user_id from request headers
    if not user_id:
        raise HTTPException(status_code=400, detail='user_id not found')
    
    # Check if user_id folder exists
    if os.path.exists(os.path.join('uploads', user_id)):
        raise HTTPException(status_code=400, detail=f'user with id {user_id} already exists')
    
    # Check if request contains files (at least one file)
    if not voice_files:
        raise HTTPException(status_code=400, detail='voice files not found')
    
    # Check if voice don't exists on ElevenLabs, if exists, return its voice_id
    for voice in voices():
        if voice.name == user_id:
            return JSONResponse(status_code=400, content={'status': 'error', 'message': f'voice with name {user_id} already exists', 'voice_id': voice.voice_id})
    
    ALLOWED_EXTENSIONS = ['wav', 'mp3']
    # If user has't submitted any file which is not allowed, raise error
    if not voice_files.filename.endswith(tuple(ALLOWED_EXTENSIONS)):
        raise HTTPException(status_code=400, detail='file format not supported. Only .wav files are supported')
    
    # Save files to uploads/user_id folder
    os.mkdir(os.path.join('uploads', user_id))
    for file in voice_files:
        with open(os.path.join('uploads', user_id, file.filename), 'wb') as f:
            f.write(file.file.read())
    
    # Clone voice and return voice_id
    folder_path = os.path.join('uploads', user_id)
    voice = clone(
        name=user_id,
        description=f'Voice of {user_id} generated on {datetime.now()}',
        files=[os.path.relpath(os.path.join(folder_path, file)) for file in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, file))]
    )
    return JSONResponse(status_code=200, content={'status': 'success', 'message': 'voice added successfully', 'voice_id': voice.voice_id})

@app.post('/api/generate_voice')
async def generate_voice(
    user_id: str = Header(),
    input_speech: UploadFile = File(...)
):
    """Generate voice from text"""
    # Get user_id from request headers
    if not user_id:
        raise HTTPException(status_code=400, detail='user_id not found')
    
    # Get text from request headers
    if not input_speech:
        raise HTTPException(status_code=400, detail='input_speech not found')
    
    # Save input_speech to uploads/user_id folder
    file_name = f'{uuid4()}.wav'
    with open(os.path.join('uploads', 'input_speech', file_name), 'wb') as f:
        f.write(input_speech.file.read())
    
    transcript = client.audio.translations.create(
        model="whisper-1",
        file=open(os.path.join('uploads', 'input_speech', file_name), 'rb'),
    )
    audio = generate(
        voice=user_id,
        text=transcript.text,
    )
    with open(os.path.join('uploads', 'output_speech', file_name), 'wb') as f:
        f.write(audio)
        
    return FileResponse(os.path.join('uploads', 'output_speech', file_name), media_type="audio/wav")

# @app.websocket('/api/input_stream')
# async def input_stream(websocket: WebSocket):
#     """Input Stream"""
#     await websocket.accept()
#     while True:
#         data = await websocket.receive_bytes()
#         await websocket.send_text(f'received {len(data)} bytes')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)