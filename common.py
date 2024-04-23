import subprocess

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv
from minio import Minio
from singleton_decorator import singleton

from config import settings

load_dotenv()


@singleton
class SpeechService:
    def __init__(self):
        self.speech_config = self._get_speech_config()
        self.speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config
        )

    def _get_speech_config(self):
        speech_config = speechsdk.SpeechConfig(
            subscription=settings.SPEECH_CONFIG_SUB_ID,
            region=settings.SPEECH_CONFIG_REGION,
        )
        speech_config.speech_synthesis_voice_name = settings.SPEECH_CONFIG_VOICE
        speech_config.endpoint_id = settings.SPEECH_CONFIG_ENDPOINT
        speech_config.set_property_by_name("OPENSSL_DISABLE_CRL_CHECK", "true")

        print(settings.SPEECH_CONFIG_SUB_ID)
        print(settings.SPEECH_CONFIG_REGION)
        print(settings.SPEECH_CONFIG_VOICE)
        print(settings.SPEECH_CONFIG_ENDPOINT)

        # use low bitrate to reduce the size of the audio file
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio24Khz160KBitRateMonoMp3
        )
        return speech_config

    def synthesize_speech(self, text):
        result = self.speech_synthesizer.speak_text_async(text).get()
        if result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            reason_text = "Cancellation reason: {}".format(cancellation_details.reason)
            print(f"reason_text: {reason_text}")
            error_details = (
                "Error details: {}".format(cancellation_details.error_details)
                if cancellation_details.error_details
                else "No error details available."
            )
            print(f"error_details: {error_details}")
        return result


class MinioUploader:
    def __init__(self, endpoint, access_key, secret_key, secure=False):
        self.minio_client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure
        )

    def upload(self, bucket_name, object_name, file_path):
        try:
            # Upload file to MinIO
            self.minio_client.fput_object(bucket_name, object_name, file_path)
            print("File uploaded successfully.")
            return f"{settings.MINIO_BASE_URL}/{bucket_name}/{object_name}"
        except Exception as err:
            print(f"Error: {err}")


def merge_ts_files_with_audio(input_files, audio, output_file, audio_mixed=False):
    tmp_file = output_file if not audio_mixed else "temp.mp4"
    concat_cmd = [
        "ffmpeg",
        "-i",
        "concat:" + "|".join(input_files),
        "-c",
        "copy",
        "-bsf:a",
        "aac_adtstoasc",
        tmp_file,
    ]
    subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not audio_mixed:
        return tmp_file
    mix_cmd = [
        "ffmpeg",
        "-i",
        tmp_file,
        "-i",
        audio,
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        output_file,
    ]
    subprocess.run(mix_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["rm", tmp_file])

    return output_file


#
# if __name__ == "__main__":
#     # Example usage
#     speech_service = SpeechService()
#     audio = speech_service.synthesize_speech("Hello, world!")
#     audio_file = f"{uuid.uuid4()}.mp3"
#     output_file = f"{uuid.uuid4()}.mp4"
#     with open(audio_file, "wb") as f:
#         f.write(audio.audio_data)
#
#     channel = "loki"
#     # Connect to Redis server
#     r = redis.Redis(host="192.168.50.178", port=6378, db=0)
#     videos_indexes = range(337)
#     edited_url = "playlist{}.ts"
#     sq_len = math.ceil(audio.audio_duration.total_seconds() / 0.5)
#     sq_min = random.randint(0, 300)
#     print(sq_len)
#     selected_edited = sorted(videos_indexes[sq_min : sq_min + sq_len])
#     selected_files = [edited_url.format(str(i).zfill(3)) for i in selected_edited]
#     print(selected_files)
#     merge_ts_files_with_audio(selected_files, audio_file, output_file)
#     # Publish messages to the channel
#     message = json.dumps({"lip_synced": selected_files})
#     r.publish(channel, message)
