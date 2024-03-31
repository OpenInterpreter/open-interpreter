import logging
import os
import queue
import threading

from .oi_dir import oi_dir

log = logging.getLogger(__name__)


# We probably want to decouple HistoryAutosave from oi_dir
def history_autosaver(hist_filepath=os.path.join(oi_dir, "terminal.hist")):
    try:
        import readline

        class HistoryAutosaver:
            # Messages queue
            _q: queue.Queue
            _thread: threading.Thread

            def __init__(self):
                self._q = queue.Queue()
                self._run()

            def add(self, msg, blocking=False):
                if blocking:
                    readline.write_history_file(hist_filepath)
                else:
                    self._q.put(msg)

            def _load(self):
                try:
                    readline.read_history_file(hist_filepath)
                except FileNotFoundError:
                    pass

            def _run(self):
                readline.set_auto_history(True)  # Maybe redundant
                self._thread = threading.Thread(target=self._loop, daemon=True)
                self._thread.start()

            def _loop(self):
                readline.read_history_file(hist_filepath)
                while True:
                    log.debug("Waiting for history to write")
                    msg = self._q.get()
                    if msg is None:
                        break
                    try:
                        readline.append_history_file(1, hist_filepath)
                    except FileNotFoundError:
                        readline.write_history_file(hist_filepath)
                    log.debug("History written to " + hist_filepath)

            def __del__(self):
                # Is this redundant?
                try:
                    log.debug("Closing history manager")
                    self._thread.join()
                except:
                    pass

    except ImportError:
        log.warning("readline module not found, history autosave disabled")

        class HistoryAutosaver:
            pass

    return HistoryAutosaver()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    handle = history_autosaver()
    while True:
        cmd = input("")
        handle.add(cmd)
