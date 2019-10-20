import abc


class Button(object, metaclass=abc.ABCMeta):
    """ Interface for button """

    @abc.abstractmethod
    def on_event(self, loop, callback):
        """
        Define the callback for events.
        callback is cb(event, time).
        The callback is called on the provided event loop, with
        loop.call_soon_threadsafe
        """
        raise NotImplementedError("Should have implemented")
