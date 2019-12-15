import asyncio
import selectors
import os
import logging
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from .ears import Ears


class EarsDev(Ears):
    """
    Implementation for ears based on /dev/ear*.
    Relying on tagtagtag-ears driver.
    """

    def __init__(self):
        self.fds = [None, None]
        self.callback = None
        self.positions = [None, None]
        for i in range(0, 2):
            ear = os.open("/dev/ear" + str(i), os.O_RDWR)
            try:
                os.write(ear, b"?")
                self.fds[i] = ear
                asyncio.get_event_loop().add_reader(ear, self._do_read, i)
            except:
                logging.error(f"ear {i} is apparently broken")
                os.close(ear)
        self.executor = ThreadPoolExecutor(max_workers=1)
        # Lock preventing detection and move operations happening
        # simultaneously
        self.lock = asyncio.Lock()

    def _do_read(self, ear):
        logging.debug(f"do_read from {ear}")
        byte = os.read(self.fds[ear], 1)
        if len(byte) == 0:
            # EOF, ear is broken.
            logging.error(f"ear {ear} has been declared broken")
            fd = self.fds[ear]
            asyncio.get_event_loop().remove_reader(fd)
            os.close(fd)
            self.positions[ear] = None
            self.fds[ear] = None
        else:
            logging.debug(f"do_read from {ear} => {byte[0]}")
            if byte == b"m":
                logging.debug(f"do_read from {ear} => invoking callback")
                if self.callback:
                    (loop, callback) = self.callback
                    loop.call_soon_threadsafe(lambda ear=ear: callback(ear))
            elif byte == b"\xff":
                logging.debug(f"do_read from {ear} => position is unknown")
                self.positions[ear] = None
            else:
                logging.debug(f"do_read from {ear} => position is {byte[0]}")
                self.positions[ear] = byte[0]

    def on_move(self, loop, callback):
        """
        Define the callback for ears events.
        callback is cb(ear) with ear being LEFT_EAR or RIGHT_EAR.
        The callback is called on the provided event loop, with
        loop.call_soon_threadsafe
        """
        self.callback = (loop, callback)

    async def reset_ears(self, target_left, target_right):
        """ Reset the ears to a known position """
        async with self.lock:
            await asyncio.get_event_loop().run_in_executor(
                self.executor, self._do_reset_ears, target_left, target_right
            )

    def _do_reset_ears(self, target_left, target_right):
        """
        Reset ears by running a detection and ignoring the result.
        Thread: executor
        Lock: acquired
        """
        if self.fds[0] is not None:
            os.write(self.fds[0], b">" + bytes([target_left]))
        if self.fds[1] is not None:
            os.write(self.fds[1], b">" + bytes([target_right]))

    async def move(self, motor, delta, direction):
        """
        Move an ear by a delta (position) in a direction.
        May run a complete turn.
        Returns before ear reached requested position.
        """
        async with self.lock:
            await asyncio.get_event_loop().run_in_executor(
                self.executor, self._do_move, motor, delta, direction
            )

    def _do_move(self, motor, delta, direction):
        """
        Move a given ear by a delta in a given direction.
        Thread: executor
        Lock: acquired
        """
        if direction:
            cmd = b"-"
        else:
            cmd = b"+"
        logging.debug(f"_do_move")
        if self.fds[motor] is not None:
            os.write(self.fds[motor], cmd + bytes([delta]))

    async def wait_while_running(self):
        """
        Wait until both ears stopped.
        """
        async with self.lock:
            await asyncio.get_event_loop().run_in_executor(
                self.executor, self._do_wait_while_running
            )

    def _do_wait_while_running(self):
        """
        Wait until motors are no longer running, sending a blocking NOP to ears.
        Thread: executor
        Lock: acquired
        """
        logging.debug(f"_do_wait_while_running")
        if self.fds[0] is not None:
            os.write(self.fds[0], b".")
        if self.fds[1] is not None:
            os.write(self.fds[1], b".")

    def get_positions(self):
        """
        Get the position of the ears, without running any detection
        (simply return cached positions)
        """
        return (self.positions[0], self.positions[1])

    async def detect_positions(self):
        """
        Get the position of the ears, running a detection if required.
        """
        async with self.lock:
            await asyncio.get_event_loop().run_in_executor(
                self.executor, self._do_detect_positions
            )
            return (self.positions[0], self.positions[1])

    def _do_detect_positions(self):
        """
        Get the position of the ears, running a detection if required.
        Thread: executor
        Lock: acquired
        """
        logging.debug(f"do_detect_positions")
        if self.fds[0] is not None:
            os.write(self.fds[0], b"!")
        if self.fds[1] is not None:
            os.write(self.fds[1], b"!")
        self._do_wait_while_running()

    async def go(self, ear, position, direction):
        """
        Go to a specific position.
        If direction is 0, turn forward, otherwise, turn backward
        If position is not within 0-16, it represents additional turns.
        For example, 17 means to position the ear at 0 after at least a
        complete turn.
        Returns before ear reached requested position.
        """
        async with self.lock:
            await asyncio.get_event_loop().run_in_executor(
                self.executor, self._do_go, ear, position, direction
            )

    def _do_go(self, ear, position, direction):
        """
        Actually go to a specific position.
        Lock: acquired.
        """
        logging.debug(f"do_go {ear}")
        if direction:
            cmd = b"<"
        else:
            cmd = b">"
        if self.fds[ear] is not None:
            os.write(self.fds[ear], cmd + bytes([position]))

    def is_broken(self, ear):
        """
        Determine if ear is apparently broken
        """
        return self.fds[ear] is None
