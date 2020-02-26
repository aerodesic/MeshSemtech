# Simple thread class
import _thread
from ulock import lock
from gc import collect

class thread():
    def __init__(self, name="sx127x", stack=None, run=None):
        self._stack = stack
        self._name = name
        self._runninglock = lock()
        self._rc = None
        self.running = False
        self._ident = None
        self._userrun = run

    # Return the name of the thread
    def name(self):
        return self._name

    def ident(self):
        return self._ident

    def __str__(self):
        return "%s:%s" % (self._name, self._ident)

    # Start the thread execution
    def start(self, *args, **kwargs):
        if self._runninglock.acquire(0):
            self.running = True
            if self._stack != None:
                _thread.stack_size(self._stack)
            _thread.start_new_thread(self._run, args, kwargs)

    # Calls user 'run' method and saves return code
    def _run(self, *args, **kwargs):
        # Capture our ident
        self._ident = _thread.get_ident()

        # Run the user's code
        if self._userrun:
            self._rc = self._userrun(self, *args, **kwargs)
        else:
            self._rc = self.run(*args, **kwargs)
        self._ident = None

        # Allow 'wait' to finish
        self._runninglock.release()

    # Set flag to stop the thread
    def stop(self):
        self.running = False

    # Wait for thread to terminate if wait is 1 otherwise just test if terminated and return exit code
    def wait(self, wait=1):
        return self._rc if self._runninglock.acquire(wait) else None

from time import sleep
class timer(thread):
    def __init__(self, timer, func, *args, **kwargs):
        self._timer = timer
        self._args = args
        self._kwargs = kwargs
        self._func = func
        super().__init__()

    def run(self):
        sleep(self._timer)
        self._func(*self._args, **self._kwargs)
        del(self)
        collect()

