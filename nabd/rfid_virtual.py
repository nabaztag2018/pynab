from typing import Callable, Optional

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
        data: Optional[bytes],
    ):
        data_str = data.hex() if data else ""
        print(f"rfid.write({tech}, {uid.hex()}, {picture}, {app}, {data_str})")

    def enable_polling(self):
        print("rfid.enable_polling()")

    def disable_polling(self):
        print("rfid.disable_polling()")
