import _thread

# Non-recursive lock

# Stub for class of lock().  Change semantics to allow a creation of locked item.
class lock():
    def __init__(self, locked=False):
        self._lock = _thread.allocate_lock()
        if locked:
            self._lock.acquire()

        self.acquire = lambda waitflag=1, timeout=-1 : self._lock.acquire(waitflag, timeout)
        self.release = lambda : self._lock.release()
        self.locked  = lambda : self._lock.locked()

    def __enter__(self):
        self.acquire()

    def __exit__(self, type, value, traceback):
        self.release()

    
class RLockException(Exception):
    pass

# Recursive lock - allow recursive locking within same thread.
class rlock():
    def __init__(self, locked=False):
        self._lock = _thread.allocate_lock()
        if locked:
            self._lock.acquire()
        self._release = _thread.allocate_lock()
        self._release.acquire()
        self._ident = None
        self._count = 0

    def acquire(self, test=0):
        locked = True # Assume success
        with self._lock:

            if self._ident == _thread.get_ident():
                # We are the owner, so increase the count
                self._count += 1

            elif test:
                # Failed lock test
                locked = False

            else:
                # Wait for it to be released
                while self._ident != None:
                    # Unlock the access
                    self._lock.release()
                    # Wait for a release
                    self._release.acquire()
                    # Relock and try test again
                    self._lock.acquire()

                # Claim it as ours
                self._ident = _thread.get_ident()
                self._count = 1

        return locked

    def release(self):
        with self._lock:
            if self._ident == _thread.get_ident():
                self._count -= 1
                if self._release.locked():
                    self._release.release()
                if self._count == 0:
                    self._ident = None
            else:
                raise RLockException("Not held by caller")

    def locked(self):
        with self._lock:
            return self._ident == _thread.get_ident()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, type, value, traceback):
        self.release()

