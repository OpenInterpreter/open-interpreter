import json
import threading
import time

from core import OpenInterpreter


class AsyncOpenInterpreter(OpenInterpreter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.async_thread = None
        self.input_queue
        self.output_queue

    async def input(self, chunk):
        """
        Expects a chunk in streaming LMC format.
        """
        try:
            chunk = json.loads(chunk)
        except:
            pass

        if "start" in chunk:
            self.async_thread.join()
        elif "end" in chunk:
            if self.async_thread is None or not self.async_thread.is_alive():
                self.async_thread = threading.Thread(target=self.complete)
            self.async_thread.start()
        else:
            await self._add_to_queue(self._input_queue, chunk)

    async def output(self, *args, **kwargs):
        # Your async output code here
        pass
