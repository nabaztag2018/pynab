import abc
import time
from enum import Enum, unique
from threading import Thread, Lock, Condition


@unique
class Led(Enum):
    BOTTOM = 4
    RIGHT = 3  # when looking at the rabbit
    CENTER = 2
    LEFT = 1
    NOSE = 0


class Leds(object, metaclass=abc.ABCMeta):
    """ Interface for leds """

    @abc.abstractmethod
    def set1(self, led, red, green, blue):
        """
        Set the color of a given led.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    def pulse(self, led, red, green, blue):
        """
        Set a given led to pulse to a given color.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    def setall(self, red, green, blue):
        """
        Set the color of every led.
        """
        raise NotImplementedError("Should have implemented")

    def stop(self):
        """
        Stop the leds thread, if any.
        """
        pass


class LedsSoft(Leds, metaclass=abc.ABCMeta):
    """
    Base implementation with software pulsing.
    """

    PULSING_RATE = 0.200  # every 200ms
    PULSING_STEPS = 10  # number of steps to reach target color

    def __init__(self):
        self.condition = Condition()
        self.pending = []
        self.pulsing = {}
        self.pending_lock = Lock()
        self.last_pulse = None
        self.running = True
        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        with self.condition:
            while self.running:
                show = False
                with self.pending_lock:
                    for cmd, led, (r, g, b) in self.pending:
                        if cmd == "pulse":
                            self.do_set(led, 0, 0, 0)
                            show = True
                            if self.last_pulse is None:
                                self.last_pulse = time.time()
                            color_incr = (
                                r / LedsSoft.PULSING_STEPS,
                                g / LedsSoft.PULSING_STEPS,
                                b / LedsSoft.PULSING_STEPS,
                            )
                            self.pulsing[led] = (
                                (r, g, b),
                                (0, 0, 0),
                                1,
                                color_incr,
                            )
                        elif cmd == "set":
                            if led in self.pulsing:
                                del self.pulsing[led]
                            self.do_set(led, r, g, b)
                            show = True
                    self.pending = []
                next_pulse = None
                if len(self.pulsing) > 0:
                    now = time.time()
                    next_pulse = self.last_pulse + LedsSoft.PULSING_RATE
                    if now >= next_pulse:
                        self.last_pulse = next_pulse
                        next_pulse = next_pulse + LedsSoft.PULSING_RATE
                        new_pulsing = {}
                        for led, pulse in self.pulsing.items():
                            (
                                target,
                                (current_r, current_g, current_b),
                                direction,
                                incr,
                            ) = pulse
                            (target_r, target_g, target_b) = target
                            (incr_r, incr_g, incr_b) = incr
                            if (
                                direction == 1
                                and target_r == int(current_r)
                                and target_g == int(current_g)
                                and target_b == int(current_b)
                            ):
                                direction = -1
                            elif (
                                direction == -1
                                and int(current_r) == 0
                                and int(current_g) == 0
                                and int(current_b) == 0
                            ):
                                direction = 1
                            if direction == 1:
                                new_r = min(current_r + incr_r, target_r)
                                new_g = min(current_g + incr_g, target_g)
                                new_b = min(current_b + incr_b, target_b)
                            else:
                                new_r = max(current_r - incr_r, 0)
                                new_g = max(current_g - incr_g, 0)
                                new_b = max(current_b - incr_b, 0)
                            self.do_set(
                                led, int(new_r), int(new_g), int(new_b)
                            )
                            show = True
                            new_pulsing[led] = (
                                target,
                                (new_r, new_g, new_b),
                                direction,
                                incr,
                            )
                        self.pulsing = new_pulsing
                else:
                    self.last_pulse = None
                if show:
                    self.do_show()
                timeout = None
                if next_pulse is not None:
                    delta = next_pulse - time.time()
                    timeout = max(0, delta)
                self.condition.wait(timeout=timeout)

    def set1(self, led, red, green, blue):
        with self.pending_lock:
            self.pending.append(("set", led, (red, green, blue)))
        with self.condition:
            self.condition.notify()

    def pulse(self, led, red, green, blue):
        with self.pending_lock:
            self.pending.append(("pulse", led, (red, green, blue)))
        with self.condition:
            self.condition.notify()

    def setall(self, red, green, blue):
        with self.pending_lock:
            for led in list(Led):
                self.pending.append(("set", led, (red, green, blue)))
        with self.condition:
            self.condition.notify()

    def stop(self):
        with self.condition:
            self.running = False
            self.condition.notify()
        self.thread.join()

    @abc.abstractmethod
    def do_set(self, led, red, green, blue):
        """
        Actually set a led.
        """
        pass

    @abc.abstractmethod
    def do_show(self):
        """
        Show all leds at once.
        """
        pass
