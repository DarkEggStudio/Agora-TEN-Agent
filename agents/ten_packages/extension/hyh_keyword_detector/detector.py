#
#
#
import asyncio
import threading
import base64
from datetime import datetime
from typing import Awaitable
from functools import partial

from ten import (
    AudioFrame,
    VideoFrame,
    Extension,
    TenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from ten.audio_frame import AudioFrameDataFmt
from .log import logger

DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"

REALTIME_PAUSE_KEYWORD = "Wait a minute"
REALTIME_START_KEYWORD = "Restart please"

CMD_REALTIME_PAUSE = "pause_realtime_v2v"
CMD_REALTIME_START = "start_realtime_v2v"

class KeywordDetector(Extension):
    def __init__(self, name: str):
        super().__init__(name)

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("KeywordDetectorExtension on_start")
        ten_env.on_start_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("on_deinit")
        ten_env.on_deinit_done()

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        is_final = self.get_property_bool(data, DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL)
        input_text = self.get_property_string(data, DATA_IN_TEXT_DATA_PROPERTY_TEXT)
        if not is_final:
            logger.info("ignore non-final input")
            return
        if not input_text:
            logger.info("ignore empty text")
            return

        logger.info(f"OnData input text: [{input_text}]")
        # check keyword
        result = input_text.find(REALTIME_PAUSE_KEYWORD)
        if result != -1:
            # send pause cmd
            logger.info(f"Send cmd: {CMD_REALTIME_PAUSE}")
            ten_env.send_cmd(Cmd.create(CMD_REALTIME_PAUSE), None)
            return

        result = input_text.find(REALTIME_START_KEYWORD)
        if result != -1:
            # send start cmd
            logger.info(f"Send cmd: {CMD_REALTIME_START}")
            ten_env.send_cmd(Cmd.create(CMD_REALTIME_START), None)
            return
        pass
    
    def on_cmd(self, ten_env, cmd):
        pass
    
    def on_audio_frame(self, ten_env, audio_frame):
        pass

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("KeywordDetectorExtension on_stop")

    def get_property_bool(data: Data, property_name: str) -> bool:
        """Helper to get boolean property from data with error handling."""
        try:
            return data.get_property_bool(property_name)
        except Exception as err:
            logger.warn(f"GetProperty {property_name} failed: {err}")
            return False