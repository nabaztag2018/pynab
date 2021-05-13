from .ears import Ears


class EarsVirtual(Ears):  # pragma: no cover
    def __init__(self, nabio_virtual):
        self.loop = None
        self.callback = None
        self.left = 0
        self.right = 0
        self.nabio_virtual = nabio_virtual

    def on_move(self, loop, callback):
        self.loop = loop
        self.callback = callback

    async def reset_ears(self, target_left, target_right):
        self.left = target_left
        self.right = target_right
        self.nabio_virtual.update_rabbit()

    async def move(self, ear, delta, direction):
        if direction:
            abs_delta = -delta
        else:
            abs_delta = delta
        if ear == Ears.LEFT_EAR:
            self.left = (self.left + abs_delta) % Ears.STEPS
        else:
            self.right = (self.right + abs_delta) % Ears.STEPS
        self.nabio_virtual.update_rabbit()

    async def get_positions(self):
        return (self.left, self.right)

    async def detect_positions(self):
        return (self.left, self.right)

    async def go(self, ear, position, direction):
        if ear == Ears.LEFT_EAR:
            self.left = position % Ears.STEPS
        else:
            self.right = position % Ears.STEPS
        self.nabio_virtual.update_rabbit()

    async def wait_while_running(self):
        pass

    async def is_broken(self, ear):
        return False
