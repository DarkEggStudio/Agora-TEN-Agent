#
#
#
import asyncio
import threading
import base64
from datetime import datetime
from typing import Awaitable
from functools import partial
from collections import deque

from ten import (
    # AudioFrame,
    # VideoFrame,
    Extension,
    TenEnv,
    Cmd,
    # StatusCode,
    # CmdResult,
    Data,
)
# from ten.audio_frame import AudioFrameDataFmt
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

        self.loop = asyncio.new_event_loop()
        self.thread: threading.Thread = None

    # memory = []
    # loop = None
    # queue = AsyncQueue()

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("on_init")
        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("KeywordDetectorExtension on_start")

        def start_event_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()
        self.thread = threading.Thread(
            target=start_event_loop, args=(self.loop,))
        self.thread.start()
        #asyncio.run_coroutine_threadsafe(self._init_connection(), self.loop)

        # self.loop = asyncio.new_event_loop()
        # def start_loop():
        #     asyncio.set_event_loop(self.loop)
        #     self.loop.run_forever()
        # threading.Thread(target=start_loop, args=[]).start()

        self.loop.create_task(self._process_queue(ten_env))

        ten_env.on_start_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("on_deinit")
        ten_env.on_deinit_done()

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        logger.info("[HYH] OnData input text")
        is_final = self.get_property_bool(data, DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL)
        input_text = self.get_property_string(data, DATA_IN_TEXT_DATA_PROPERTY_TEXT)
        if not is_final:
            logger.info("[HYH] ignore non-final input")
            return
        if not input_text:
            logger.info("[HYH] ignore empty text")
            return

        logger.info(f"[HYH] OnData input text: [{input_text}]")
        # check keyword
        result = input_text.find(REALTIME_PAUSE_KEYWORD)
        if result != -1:
            # send pause cmd
            logger.info(f"[HYH] Send cmd: {CMD_REALTIME_PAUSE}")
            ten_env.send_cmd(Cmd.create(CMD_REALTIME_PAUSE), None)
            return

        result = input_text.find(REALTIME_START_KEYWORD)
        if result != -1:
            # send start cmd
            logger.info(f"[HYH] Send cmd: {CMD_REALTIME_START}")
            ten_env.send_cmd(Cmd.create(CMD_REALTIME_START), None)
            return
        pass
    
    def on_cmd(self, ten_env, cmd):
        pass
    
    def on_audio_frame(self, ten_env, audio_frame):
        pass

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("KeywordDetectorExtension on_stop")
        ten_env.on_stop_done()

    def get_property_bool(self, data: Data, property_name: str) -> bool:
        """Helper to get boolean property from data with error handling."""
        try:
            return data.get_property_bool(property_name)
        except Exception as err:
            logger.warning(f"GetProperty {property_name} failed: {err}")
            return False
            
    def get_property_string(self, data: Data, property_name: str) -> str:
        """Helper to get string property from data with error handling."""
        try:
            return data.get_property_string(property_name)
        except Exception as err:
            logger.warning(f"GetProperty {property_name} failed: {err}")
            return ""

    async def _process_queue(self, ten_env: TenEnv):
        """Asynchronously process queue items one by one."""
        while True:
            # Wait for an item to be available in the queue
            [task_type, message] = await self.queue.get()
            try:
                # Create a new task for the new message
                self.current_task = asyncio.create_task(self._run_chatflow(ten_env, task_type, message, self.memory))
                await self.current_task  # Wait for the current task to finish or be cancelled
            except asyncio.CancelledError:
                logger.info(f"Task cancelled: {message}")
                
# class AsyncQueue:
#     def __init__(self):
#         self._queue = deque()  # Use deque for efficient prepend and append
#         self._condition = asyncio.Condition()  # Use Condition to manage access

#     async def put(self, item, prepend=False):
#         """Add an item to the queue (prepend if specified)."""
#         async with self._condition:
#             if prepend:
#                 self._queue.appendleft(item)  # Prepend item to the front
#             else:
#                 self._queue.append(item)  # Append item to the back
#             self._condition.notify() 

#     async def get(self):
#         """Remove and return an item from the queue."""
#         async with self._condition:
#             while not self._queue:
#                 await self._condition.wait()  # Wait until an item is available
#             return self._queue.popleft()  # Pop from the front of the deque

#     async def flush(self):
#         """Flush all items from the queue."""
#         async with self._condition:
#             while self._queue:
#                 self._queue.popleft()  # Clear the queue
#             self._condition.notify_all()  # Notify all consumers that the queue is empty

#     def __len__(self):
#         """Return the current size of the queue."""
#         return len(self._queue)
