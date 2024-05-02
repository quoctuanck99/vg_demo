import io

import livekit
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware

load_dotenv()

from config import settings
import azure.cognitiveservices.speech as speechsdk
import json
import time
import uuid
from typing import Annotated
from pydub import AudioSegment

from fastapi import FastAPI, HTTPException, Response, Form, Request
import redis
import httpx
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from common import SpeechService, MinioUploader, AudioStreamCallback

app = FastAPI()
redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
speech_service = SpeechService()
videos_indexes = range(337)
minio_uploader = MinioUploader(
    endpoint=settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=False,
)
client = httpx.AsyncClient()

resource = Resource(attributes={"service.name": "demo_webrtc"})
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)
otlp_exporter = OTLPSpanExporter(endpoint=settings.OTLP_ENDPOINT, insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)


async def send_llm_request(text):
    headers = {"Content-Type": "application/json"}

    data = {
        "channel_id": "83c59158-2c45-4f2d-bf57-15dc0ba5d81d_49782ea9-9ad4-41ce-b1ae-77ab8678c72c",
        "user_id": 1079,
        "group_id": 5567,
        "chat_message_id": 126616,
        "language_code": "en",
        "time_zone": "America/Los_Angeles",
        "is_streaming": True,
        "avatar_code": "reimi",
        "stream": True,
        "message": text,
        "video_id": "C0506",
    }
    response = await client.post(settings.LLM_API_URL, headers=headers, json=data)
    content = response.content.decode("utf8")
    content = content.replace("}{", "}<sep>{")
    json_objects = content.split("<sep>")
    sentences = ""
    for obj in json_objects:
        o = json.loads(obj)
        sentences += o["data"]
    print(response.text)
    return sentences


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.get("/stream/{key}")
async def get_data(key: str):
    key = key.split(".")[0]
    # Retrieve data from Redis
    data = redis_client.get(key)
    if data:
        # Set the appropriate content type and return the data directly
        response = Response(content=data)
        response.headers["Content-Disposition"] = f"attachment; filename={key}.m3u8"
        return response
    else:
        raise HTTPException(status_code=404, detail="Data not found")


async def generate_lip_synced(message, channel="abc"):
    audio_file_name = f"{uuid.uuid4()}.wav"
    output_file_name = f"{uuid.uuid4()}.mp4"
    audio_file = f"{settings.MEDIA_PATH}/{audio_file_name}"
    output_file = f"{settings.MEDIA_PATH}/{output_file_name}"
    with tracer.start_as_current_span("process-tts"):
        audio_stream = speechsdk.audio.PushAudioOutputStream(
            AudioStreamCallback(channel)
        )
        audio_config = speechsdk.audio.AudioOutputConfig(stream=audio_stream)
        speech_service.init_synthesizer(audio_config)
        audio = speech_service.synthesize_speech(message)
    # sound = AudioSegment.from_mp3(io.BytesIO(audio.audio_data))
    # sound.export(audio_file, format="wav")
    print("audio.audio_duration", str(audio.audio_duration.total_seconds()))
    # with tracer.start_as_current_span("process-tts-merge-video-audio"):
    #     sq_len = math.ceil(audio.audio_duration.total_seconds() / 0.5)
    #     sq_min = int(
    #         redis_client.get("index") if redis_client.get("index") else 0
    #     ) + int(0.5 * 2)
    #     sq_max = sq_min + sq_len
    #     print("sq_len", str(sq_len))
    #     selected_edited = sorted(videos_indexes[sq_min:sq_max])
    #     selected_files = [
    #         settings.EDITED_PATH.format(str(i).zfill(3)) for i in selected_edited
    #     ]
    #     print("selected_files", str(selected_files))
    #     merge_ts_files_with_audio(selected_files, audio_file, output_file, False)
    result = {
        "total_seconds": audio.audio_duration.total_seconds(),
        "text": message,
    }
    # with tracer.start_as_current_span("process-upload-to-s3"):
    #     uploaded_url = minio_uploader.upload(
    #         bucket_name="videos",
    #         object_name=f"output/{output_file_name}",
    #         file_path=output_file,
    #     )
    #     result["video"] = uploaded_url
    #     # print("Uploaded video URL:", uploaded_url)
    #     uploaded_url = minio_uploader.upload(
    #         bucket_name="videos",
    #         object_name=f"output/{audio_file_name}",
    #         file_path=audio_file,
    #     )
    #     result["audio"] = uploaded_url
    #     print("Uploaded audio URL:", uploaded_url)
    # subprocess.run(["rm", output_file])
    # subprocess.run(["rm", audio_file])
    return result


@app.post("/livekit-token")
async def talk_with_llm(room_id: Annotated[str, Form()]):
    token = livekit.AccessToken(
        settings.LIVEKIT_API_KEY,
        settings.LIVEKIT_API_SECRET,
        identity=room_id,
        grant=livekit.VideoGrant(
            room_join=True,
            room=room_id,
        ),
    )

    return {"wss": settings.LIVEKIT_WSS_URL, "token": token.to_jwt()}


@app.post("/talk")
async def talk_from_text(
    message: Annotated[str, Form()], room_id: Annotated[str, Form()]
):
    with tracer.start_as_current_span("/talk"):
        with tracer.start_as_current_span("process-lip-synced"):
            result = await generate_lip_synced(message, room_id)
        # Publish messages to the channel
        # message = json.dumps(result)
        # print(f"publish message {message} to lip:synced:{room_id}")
        # redis_client.publish(f"lip:synced:{room_id}", message)
        return result


@app.post("/chat")
async def talk_with_llm(
    message: Annotated[str, Form()], room_id: Annotated[str, Form()]
):
    with tracer.start_as_current_span("/chat"):
        channel = "loki"
        with tracer.start_as_current_span("process-llm"):
            answer = await send_llm_request(message)
        with tracer.start_as_current_span("process-lip-synced"):
            result = await generate_lip_synced(answer)
        # Publish messages to the channel
        message = json.dumps(result)
        redis_client.publish(
            settings.LIVEKIT_AGENTS_AUDIO_CHANNEL.format(room_id), message
        )
        return result


origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:8443",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
