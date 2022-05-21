from typing import Callable

from .rfid import Rfid, TagFlags, TagTechnology


class RfidVirtual(Rfid):
    def on_detect(
        self,
        loop,
        callback: Callable[
            [TagTechnology, bytes, int, int, bytes, TagFlags, dict], None
        ],
    ) -> None:
        self.loop = loop
        self.callback = callback

    def write(
        self,
        tech: TagTechnology,
        uid: bytes,
        picture: int,
        app: int,
        data: bytes,
    ):
        print(f"rfid.write({tech}, {uid}, {picture}, {app}, {data})")

    def enable_polling(self):
        print("rfid.enable_polling()")

    def disable_polling(self):
        print("rfid.disable_polling()")
