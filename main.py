import os
import threading
import time
import uuid

import redis

MEDIA_PLAYLIST_LAYOUT = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:1
#EXT-X-MEDIA-SEQUENCE:{0}
{1}
"""


ROOT_PATH = "/data/source"
MEDIA_URL = "http://192.168.50.178:1234"


class RedisStorage:
    def __init__(self):
        self.__redis_cli = redis.Redis(host="localhost", port=6378, db=9)

    def save_file(self, key, data):
        self.__redis_cli.set(key, data)


class StreamWriter:
    def __init__(self):
        self.__video_code = "C0501"
        self.__source_stream = []
        self.__init_playlist_files()
        self.__pointer: int = 0
        self.__window_size = 5
        self.__main_stream = []
        self.__storage = RedisStorage()
        self.__key = "f1f4e6e9-ae49-431f-9e80-631be03c6484"

    def __init_playlist_files(self):
        self.__source_stream = [
            i for i in os.listdir(f"{ROOT_PATH}/{self.__video_code}") if ".ts" in i
        ]
        self.__source_stream.sort()
        self.__source_stream = self.__source_stream
        print(self.__source_stream)

    def __write_playlist(self):
        while True:
            playlists = ""
            for i in self.__main_stream:
                if i == "#EXT-X-DISCONTINUITY":
                    playlists = playlists + f"{i}\n"
                else:
                    playlists = (
                        playlists + f"#EXTINF:0.5,\n{MEDIA_URL}/{self.__video_code}/{i}\n"
                    )
            file_content = MEDIA_PLAYLIST_LAYOUT.format(self.__pointer, playlists)
            self.__storage.save_file(self.__key, file_content)

            print(f"playlist updated when pointer = {self.__pointer}")
            time.sleep(0.5)

    def __playlist_move(self):
        while True:
            print(f"pointer={self.__pointer}")
            index = self.__pointer % len(self.__source_stream)
            if index + self.__window_size < len(self.__source_stream):
                self.__main_stream = self.__source_stream[
                    index : (index + self.__window_size)
                ]
            else:
                self.__main_stream = ["#EXT-X-DISCONTINUITY"] + (self.__source_stream[index:] +
                                      self.__source_stream[:self.__window_size - len(self.__source_stream) + index])
            self.__pointer += 1
            time.sleep(0.5)

    def run(self):
        # Start playlist_move in a separate thread
        move_thread = threading.Thread(target=self.__playlist_move)
        move_thread.start()
        # Start write_playlist in another separate thread
        write_thread = threading.Thread(target=self.__write_playlist)
        write_thread.start()


writer = StreamWriter()
writer.run()
