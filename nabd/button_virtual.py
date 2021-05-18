from .button import Button


class ButtonVirtual(Button):
    """Interface for button"""

    def on_event(self, loop, callback):
        self.loop = loop
        self.callback = callback
