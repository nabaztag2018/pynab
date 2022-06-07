import asyncio
import datetime
import logging
import subprocess
import sys
from typing import List

from dateutil import tz

from nabcommon import nabservice

from . import rfid_data


class NabClockd(nabservice.NabService):
    DAEMON_PIDFILE = "/run/nabclockd.pid"

    def __init__(self):
        super().__init__()
        from . import models

        self.config = models.Config.load()
        self.loop_cv = asyncio.Condition()
        self.asleep = None
        self.last_chime = None
        self.current_tz = self.get_system_tz()
        self.__synchronized_since_boot = False
        self.__boot_date = None
        self.last_time_idle_state = None
        self.ignore_next_idle_packet = False

    async def reload_config(self):
        from . import models

        async with self.loop_cv:
            self.config = await models.Config.load_async()
            self.loop_cv.notify()

    def synchronized_since_boot(self):
        """
        Determine whether the clock was synchronized since boot using uptime
        and /run/systemd/timesync/synchronized
        see systemd-timesyncd.service(8)
        Both dates start with ISO 8601 strings and we can compare them
        lexically.
        """
        if self.__synchronized_since_boot:
            return True
        first_run = False
        if self.__boot_date is None:
            first_run = True
            self.__boot_date = subprocess.run(
                ["uptime", "-s"], stdout=subprocess.PIPE
            ).stdout
        synchronized_date = subprocess.run(
            ["stat", "-c", "%y", "/run/systemd/timesync/synchronized"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ).stdout
        if synchronized_date > self.__boot_date:
            self.__synchronized_since_boot = True
            if not first_run:
                logging.info("Clock has been synchronized")
            return True
        if first_run:
            logging.warning(
                "Clock is not synchronized, disabling chime & sleep"
            )
        return False

    async def chime(self, hour: int) -> None:
        now = datetime.datetime.now()
        expiration = now + datetime.timedelta(minutes=3)
        # TODO: randomly play a message from all/
        packet = (
            '{"type":"message",'
            '"signature":{"audio":["nabclockd/signature.mp3"]},'
            '"body":[{"audio":["nabclockd/' + str(hour) + '/*.mp3"]}],'
            '"expiration":"' + expiration.isoformat() + '"}\r\n'
        )
        self.writer.write(packet.encode("utf8"))
        await self.writer.drain()

    def clock_response(self, now: datetime.datetime) -> List[str]:
        response = []
        if self.synchronized_since_boot():
            should_sleep = None
            if self.config.settings_per_day:
                # Until 3am, we keep the same day name
                # to obtain the settings from the current (previous) day,
                # so the user can put until 3am for the sleep time.
                curDateValue = now + datetime.timedelta(hours=-3)
                dayOfTheWeek = curDateValue.strftime("%A").lower()
                wakeup_hour = getattr(
                    self.config, "wakeup_hour_" + dayOfTheWeek
                )
                sleep_hour = getattr(self.config, "sleep_hour_" + dayOfTheWeek)
                wakeup_min = getattr(self.config, "wakeup_min_" + dayOfTheWeek)
                sleep_min = getattr(self.config, "sleep_min_" + dayOfTheWeek)
            else:
                wakeup_hour = self.config.wakeup_hour
                sleep_hour = self.config.sleep_hour
                wakeup_min = self.config.wakeup_min
                sleep_min = self.config.sleep_min

            if (
                wakeup_hour is not None
                and sleep_hour is not None
                and wakeup_min is not None
                and sleep_min is not None
            ):
                if (wakeup_hour, wakeup_min) < (
                    sleep_hour,
                    sleep_min,
                ):
                    should_sleep = (now.hour, now.minute) < (
                        wakeup_hour,
                        wakeup_min,
                    ) or (now.hour, now.minute) >= (
                        sleep_hour,
                        sleep_min,
                    )
                else:
                    should_sleep = (now.hour, now.minute) < (
                        wakeup_hour,
                        wakeup_min,
                    ) and (now.hour, now.minute) >= (
                        sleep_hour,
                        sleep_min,
                    )
            if self.config.sleep_wakeup_override is not None:
                if should_sleep == self.config.sleep_wakeup_override:
                    response.append("clear_override")
                else:
                    should_sleep = self.config.sleep_wakeup_override
            if (
                should_sleep is not None
                and self.asleep is not None
                and should_sleep != self.asleep
            ):
                if should_sleep:
                    response.append("sleep")
                else:
                    response.append("wakeup")
            if (
                (should_sleep is None or should_sleep is False)
                and now.minute == 0
                and self.config.chime_hour
            ):
                if self.last_chime != now.hour:
                    response.append("chime")
            if now.minute > 5:  # account for time drifts
                response.append("reset_last_chime")

        return response

    async def clock_loop(self):
        try:
            async with self.loop_cv:
                while self.running:
                    try:
                        current_tz = self.get_system_tz()
                        now = datetime.datetime.now(tz=tz.gettz(current_tz))
                        if current_tz != self.current_tz:
                            now_previous_tz = datetime.datetime.now(
                                tz=tz.gettz(self.current_tz)
                            )
                            if self.last_chime == now_previous_tz.hour:
                                self.last_chime = now.hour
                            else:
                                self.last_chime = None
                            self.current_tz = current_tz
                        response = self.clock_response(now)
                        for r in response:
                            if r == "clear_override":
                                self.config.sleep_wakeup_override = None
                                await self.config.save_async()
                            elif r == "sleep":
                                # Check if we need to play the sleep sound
                                if (
                                    self.config.play_wakeup_sleep_sounds
                                    and self.last_time_idle_state
                                ):
                                    idle_elapsed_seconds = (
                                        datetime.datetime.now()
                                        - self.last_time_idle_state
                                    ).total_seconds()

                                    # Skip the sound if less than 1 second
                                    # has elapsed since the last idle packet,
                                    # that means it went to sleep
                                    # right after boot
                                    if idle_elapsed_seconds > 1:
                                        # We dont want the next idle packet
                                        # that is sent after the sound to
                                        # trigger a loop-cv-notify, so skip it
                                        self.ignore_next_idle_packet = True
                                        packet = (
                                            '{"type":"message",'
                                            '"body":[{"audio":["sleep/*.mp3"],'
                                            '"choreography":null}],'
                                            '"request_id":"sleep_sound"}\r\n'
                                        )
                                        self.writer.write(
                                            packet.encode("utf8")
                                        )
                                        await self.writer.drain()

                                self.writer.write(b'{"type":"sleep"}\r\n')
                                await self.writer.drain()
                                self.asleep = None

                            elif r == "wakeup":
                                # Check if we need to play the wakeup sound
                                if self.config.play_wakeup_sleep_sounds:
                                    # We dont want the next idle packet
                                    # that is sent after the sound to
                                    # trigger a loop-cv-notify, so skip it
                                    self.ignore_next_idle_packet = True
                                    packet = (
                                        '{"type":"message",'
                                        '"body":[{"audio":["wakeup/*.mp3"],'
                                        '"choreography":null}],'
                                        '"request_id":"wakeup_sound"}\r\n'
                                    )
                                    self.writer.write(packet.encode("utf8"))
                                    await self.writer.drain()

                                self.writer.write(b'{"type":"wakeup"}\r\n')
                                await self.writer.drain()
                                self.asleep = None
                            elif r == "chime":
                                await self.chime(now.hour)
                                self.last_chime = now.hour
                            elif r == "reset_last_chime":
                                self.last_chime = None

                        sleep_amount = 60 - now.second
                        await asyncio.wait_for(
                            self.loop_cv.wait(), sleep_amount
                        )
                    except asyncio.TimeoutError:
                        pass
        except KeyboardInterrupt:
            pass
        finally:
            if self.running:
                asyncio.get_event_loop().stop()

    def get_system_tz(self) -> str:
        with open("/etc/timezone") as w:
            return w.read().strip()

    async def process_nabd_packet(self, packet: dict) -> None:
        if (
            "type" in packet
            and packet["type"] == "state"
            and "state" in packet
            and packet["state"] != "playing"
        ):
            async with self.loop_cv:
                # If wakeup/sleep sounds are enabled and we receive
                # an idle packet ..
                if (
                    self.config.play_wakeup_sleep_sounds
                    and packet["state"] == "idle"
                ):
                    if self.ignore_next_idle_packet:
                        # .. ignore this idle packet if specified
                        self.ignore_next_idle_packet = False
                        return
                    else:
                        # .. or store the current time and continue
                        self.last_time_idle_state = datetime.datetime.now()

                self.asleep = packet["state"] == "asleep"
                self.loop_cv.notify()
        elif (
            packet["type"] == "rfid_event"
            and packet["app"] == "nabclockd"
            and packet["event"] == "detected"
        ):
            if "data" in packet:
                type = rfid_data.unserialize(packet["data"].encode("utf8"))
            else:
                type = "sleep"
            async with self.loop_cv:
                self.config.sleep_wakeup_override = type == "sleep"
                await self.config.save_async()
                self.loop_cv.notify()
        elif (
            packet["type"] == "asr_event"
            and "nlu" in packet
            and "intent" in packet["nlu"]
            and packet["nlu"]["intent"] == "nabclockd/sleep"
        ):
            async with self.loop_cv:
                self.config.sleep_wakeup_override = True
                await self.config.save_async()
                self.loop_cv.notify()
        elif packet["type"] == "button_event" and packet["event"] == "click":
            async with self.loop_cv:
                self.config.sleep_wakeup_override = False
                await self.config.save_async()
                self.loop_cv.notify()

    def start_service_loop(
        self, loop: asyncio.AbstractEventLoop
    ) -> asyncio.Task:
        return loop.create_task(self.clock_loop())

    async def stop_service_loop(self):
        async with self.loop_cv:
            self.running = False  # signal to exit
            self.loop_cv.notify()


if __name__ == "__main__":
    NabClockd.main(sys.argv[1:])
