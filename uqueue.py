from ulock import *

class QueueException(Exception):
    pass

class queue():
    def __init__(self, maxlen=0):
        self._maxlen = maxlen
        self._lock = lock()
        self._fill = lock(True)
        self._queue = []

    def __len__(self):
        with self._lock:
            return len(self._queue)

    def put(self, item):
        with self._lock:
            if self._maxlen != 0 and len(self._queue) >= self._maxlen:
                raise QueueException("full")

            self._queue.append(item)
            if self._fill.locked():
                self._fill.release()

    # Return head of queue or None if empty
    def head(self):
        with self._lock:
            return self._queue[0] if len(self._queue) != 0 else None

    # Return tail of queue or None if empty
    def tail(self):
        with self._lock:
            return self._queue[-1] if len(self._queue) != 0 else None

    def get(self, wait=1):
        self._lock.acquire()

        if wait:
            while len(self._queue) == 0:
                # Wait for something
                self._lock.release()
                self._fill.acquire()
                self._lock.acquire()

        if len(self._queue) != 0:
            item = self._queue.pop(0)
            found = True
        else:
            item = None
            found = False

        self._lock.release()

        if wait and not found:
            raise QueueException("empty")

        return item


