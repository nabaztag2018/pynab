import abc


class Ears(object, metaclass=abc.ABCMeta):
    """ Interface for ears """

    LEFT_EAR = 0
    RIGHT_EAR = 1

    FORWARD_DIRECTION = 0
    BACKWARD_DIRECTION = 1

    STEPS = 17

    @abc.abstractmethod
    def on_move(self, loop, callback):
        """
        Define the callback for ears events.
        callback is cb(ear) with ear being LEFT_EAR or RIGHT_EAR.
        The callback is called on the provided event loop, with
        loop.call_soon_threadsafe
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def reset_ears(self, target_left, target_right):
        """ Reset the ears to a known position """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def move(self, ear, delta, direction):
        """ Move by an increment in a given direction """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def get_positions(self):
        """
        Get the positions of the ears.
        Does not perform any movement to detect their positions but instead
        return None if unknown.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def detect_positions(self):
        """
        Get the positions of the ears after the user moved any.
        Perform a complete turn of user-moved ears to detect their positions.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def go(self, ear, position, direction):
        """
        Go to a specific position
        If position is not within 0-(STEPS-1), it represents additional turns.
        For example, STEPS means to position the ear at 0 after at least a
        complete turn.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def wait_while_running(self):
        """
        Wait until both motors have stopped as ears reached their target
        position
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    def is_broken(self, ear):
        """
        Determine if ear is apparently broken
        """
        raise NotImplementedError("Should have implemented")
