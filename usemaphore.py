include _thread

class SemaphoreException(Exception):
    pass

class semaphore():
    def __init__(self, maxcount=1, available=None):
        self._lock = _thread.allocate_lock()
        self._changed = _thread.allocate_lock()
        self._changed.acquire()
        self._maxcount = maxcount
        self._available = maxcount if available == None else available

    # Acquire N counts. if wait, then wait for available items; if false,just test
    def acquire(self, count=1, wait=1):
        ok = False
        with self._lock:
            if wait:
                while self._available < count:
                    self._lock.release()
                    self._changed.acquire()
                    self._lock.acquire()

            if self._available >= count:
                self._available = self._available - count
                ok = True

        return ok

    def release(self, count=1):
        with self._lock:
            new_available = self._available + count
            if new_available > self._maxcount:
                raise SemaphoreException("release")

            self._available = new_available

            if self._changed.locked():
                self._changed.release()
            
    def __enter__(self):
        self.acquire()

    def __exit__(self, type, value, traceback):
        self.release()

