import asyncio
import os
import inspect
import json
import getopt
import signal
import datetime
import time
import logging
import sys
from abc import ABC, abstractmethod
from enum import Enum
from lockfile.pidlockfile import PIDLockFile
from lockfile import AlreadyLocked, LockFailed
from nabcommon import nablogging
from nabcommon import settings

class NabService(ABC):
    PORT_NUMBER = 10543

    def __init__(self):
        settings.configure(type(self).__name__.lower())
        self.reader = None
        self.writer = None
        self.loop = None
        self.running = True
        signal.signal(signal.SIGUSR1, self.signal_handler)

    def signal_handler(self, sig, frame):
        self.loop.call_soon_threadsafe(
            lambda: self.loop.create_task(self.reload_config())
        )

    @abstractmethod
    async def reload_config(self):
        """
        Reload configuration (on USR1 signal).
        """
        pass

    async def process_nabd_packet(self, packet):
        pass

    async def client_loop(self):
        try:
            package_name = inspect.getmodule(self.__class__).__package__
            package = sys.modules[package_name]
            service_dir = os.path.dirname(inspect.getfile(self.__class__))
            asr_support = os.path.isdir(os.path.join(service_dir, "nlu"))
            rfid_support = False
            if hasattr(package, "NABAZTAG_RFID_APPLICATION_ID"):
                rfid_support = True
            if asr_support or rfid_support:
                events = []
                service_name = self.__class__.__name__.lower()
                if asr_support:
                    events.append(f'"asr/{service_name}"')
                if rfid_support:
                    events.append(f'"rfid/{service_name}"')
                events_str = ",".join(events)
                idle_packet = (
                    '{"type":"mode","mode":"idle","events":['
                    + events_str
                    + "]}\r\n"
                )
                self.writer.write(idle_packet.encode("utf8"))
            while self.running and not self.reader.at_eof():
                line = await self.reader.readline()
                if line != b"" and line != b"\r\n":
                    try:
                        packet = json.loads(line.decode("utf8"))
                        logging.debug(f"process nabd packet: {packet}")
                        await self.process_nabd_packet(packet)
                    except json.decoder.JSONDecodeError as e:
                        logging.error(
                            f"Invalid JSON packet from nabd: {line}\n{e}"
                        )
            self.writer.close()
            await self.writer.wait_closed()
        except KeyboardInterrupt:
            pass
        finally:
            if self.running:
                self.loop.run_until_complete(self.stop_service_loop())

    MAX_RETRY = 10

    def connect(self):
        self.loop = asyncio.get_event_loop()
        self._do_connect(NabService.MAX_RETRY)
        self.loop.create_task(self.client_loop())

    def _do_connect(self, retry_count):
        connection = asyncio.open_connection(
            host="127.0.0.1", port=NabService.PORT_NUMBER
        )
        try:
            (reader, writer) = self.loop.run_until_complete(connection)
            self.reader = reader
            self.writer = writer
        except ConnectionRefusedError:
            if retry_count == 0:
                print("Could not connect to server. Is nabd running?")
                logging.critical(
                    "Could not connect to server. Is nabd running?"
                )
                exit(1)
            time.sleep(1)
            self._do_connect(retry_count - 1)

    def run(self):
        self.connect()
        service_task = self.start_service_loop(self.loop)
        try:
            self.loop.run_forever()
            if service_task and service_task.done():
                ex = service_task.exception()
                if ex:
                    raise ex
        except KeyboardInterrupt:
            pass
        finally:
            self.writer.close()
            self.loop.run_until_complete(self.stop_service_loop())
            tasks = asyncio.all_tasks(self.loop)
            # give canceled tasks the last chance to run
            for t in [t for t in tasks if not (t.done() or t.cancelled())]:
                self.loop.run_until_complete(t)
            self.loop.close()

    def start_service_loop(self, loop):
        """
        Start a service loop, if any.
        Typically:
        return loop.create_task(self.service_loop())
        """
        return None

    async def stop_service_loop(self):
        """
        Signal service loop to stop.
        Typically:
        async with self.loop_cv:
            self.running = False  # signal to exit
            self.loop_cv.notify()
        """
        return None

    @classmethod
    def signal_daemon(cls):
        service_name = cls.__name__.lower()
        pidfilepath = f"/run/{service_name}.pid"
        try:
            with open(pidfilepath, "r") as f:
                pidstr = f.read()
            os.kill(int(pidstr), signal.SIGUSR1)
        # Silently ignore the fact that the daemon is not running
        except OSError:
            pass

    @classmethod
    def main(cls, argv):
        service_name = cls.__name__.lower()
        nablogging.setup_logging(service_name)
        pidfilepath = f"/run/{service_name}.pid"
        usage = (
            f"{service_name} [options]\n"
            f" -h                   display this message\n"
            f" --pidfile=<pidfile>  define pidfile (default = {pidfilepath})\n"
        )
        try:
            opts, args = getopt.getopt(argv, "h", ["pidfile="])
        except getopt.GetoptError:
            print(usage)
            exit(2)
        for opt, arg in opts:
            if opt == "-h":
                print(usage)
                exit(0)
            elif opt == "--pidfile":
                pidfilepath = arg
        pidfile = PIDLockFile(pidfilepath, timeout=-1)
        try:
            with pidfile:
                service = cls()
                service.run()
        except AlreadyLocked:
            error_msg = (
                f"{service_name} already running? (pid={pidfile.read_pid()})"
            )
            print(error_msg)
            logging.critical(error_msg)
            exit(1)
        except LockFailed:
            error_msg = (
                f"Cannot write pid file to {pidfilepath}, please fix "
                f"permissions"
            )
            print(error_msg)
            logging.critical(error_msg)
            exit(1)


class NabRecurrentService(NabService, ABC):
    """
    Base class for recurrent services that can be triggered from the website.
    Next performance time is saved in database.
    Reload configuration on USR1 signal.
    """

    class Reason(Enum):
        """
        Reason for computing next performance.
        """

        # Service just booted
        BOOT = 1
        # Service got a SIGUSR1
        CONFIG_RELOADED = 2
        # Perform was called
        PERFORMANCE_PLAYED = 3

    def __init__(self):
        super().__init__()
        self.reason = NabRecurrentService.Reason.BOOT
        self.loop_cv = asyncio.Condition()

    @abstractmethod
    async def get_config(self):
        """
        Perform a database operation to retrieve stored data and return a tuple
        with three values used by the service:

        next_date: next time the performance should happen.
        next_args: some service-specific argument for the performance.
        config: some additional configuration to be used to compute any future
        performance.

        Typical implementation is:

        from . import models
        record = await models.Config.load_async()
        config = (record.config_a, record.config_b)
        return (record.next_date, record.next_args, config)
        """
        pass

    @abstractmethod
    async def update_next(self, next_date, next_args):
        """
        Write new next date and args to database.

        Typical implementation is:
        from . import models
        record = await models.Config.load_async()
        record.next_date = next_date
        record.next_args = next_args
        await record.save_async()
        """
        pass

    @abstractmethod
    def compute_next(self, saved_date, saved_args, config, reason):
        """
        Compute next performance based on reason and config.
        Return None if no further performance should be scheduled.
        Otherwise, return tuple (next_date, next_args)

        reason (from enum Reason) describes why compute_next was invoked.
        saved_date and saved_args are current database values and could be
        returned if they are correct (typically on boot).
        config is the third value returned by get_config.

        This function should be pure (no side-effect).
        """
        pass

    @abstractmethod
    async def perform(self, expiration_date, args, config):
        """
        Perform the action.

        This function should not refer to the database.
        expiration_date is to be passed in the packet(s) written to nabd.
        args is whatever was computed by compute_next
        """
        pass

    async def reload_config(self):
        logging.info("reloading configuration")
        async with self.loop_cv:
            self.reason = NabRecurrentService.Reason.CONFIG_RELOADED
            self.loop_cv.notify()

    async def service_loop(self):
        try:
            async with self.loop_cv:
                while self.running:
                    # Load or reload configuration
                    next_date, next_args, config = await self._load_config()
                    # Determine if it's time to perform
                    now = datetime.datetime.now(datetime.timezone.utc)
                    if next_date is not None and next_date <= now:
                        await self.perform(
                            next_date + datetime.timedelta(minutes=1),
                            next_args,
                            config,
                        )
                        # reset date after performance
                        await self.update_next(None, None)
                        self.reason = (
                            NabRecurrentService.Reason.PERFORMANCE_PLAYED
                        )
                    else:
                        if next_date is None:
                            sleep_amount = None
                        else:
                            sleep_amount = (next_date - now).total_seconds()
                        try:
                            logging.info(f"reason = {self.reason}")
                            logging.info(f"sleep_amount = {sleep_amount}")
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

    def start_service_loop(self, loop):
        return loop.create_task(self.service_loop())

    async def stop_service_loop(self):
        async with self.loop_cv:
            self.running = False  # signal to exit
            self.loop_cv.notify()

    async def _load_config(self):
        """
        Load or reload configuration.
        Invokes get_config, compute_next and update_next.
        """
        saved_date, saved_args, config = await self.get_config()
        next_t = self.compute_next(saved_date, saved_args, config, self.reason)
        if next_t is None:
            next_date, next_args = None, None
        else:
            next_date, next_args = next_t
        if next_date != saved_date or next_args != saved_args:
            await self.update_next(next_date, next_args)
        return next_date, next_args, config


class NabRandomService(NabRecurrentService, ABC):
    """
    Common class for Tai Chi and Surprise.
    config is an integer passed to compute_random_delta.
    Next performance time is defined in database.
    There is no next_args.
    Reload configuration on USR1 signal.
    """

    @abstractmethod
    def compute_random_delta(self, frequency):
        """
        Return the delta (in seconds) with the next event based on frequency
        """
        pass

    def do_compute_next(self, frequency):
        """
        Actually compute next date based on random delta and current date.
        """
        if frequency == 0:
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        next_delta = self.compute_random_delta(frequency)
        return now + datetime.timedelta(seconds=next_delta)

    def compute_next(self, saved_date, saved_args, frequency, reason):
        now = datetime.datetime.now(datetime.timezone.utc)
        if saved_date is not None and saved_date < now:
            logging.info(f"compute_next saved_date < now")
            return saved_date, saved_args
        if reason == NabRecurrentService.Reason.BOOT:
            return saved_date, saved_args
        next = self.do_compute_next(frequency)
        if next is None:
            return None
        return (next, None)


class NabInfoService(NabRecurrentService, ABC):
    """
    Base class for services that display info (animations) updated on a regular
    basis from an external source (weather, air quality) and which can be
    triggered from the website.

    next_args is "info" for only updating infos, or any other text for messages
    (e.g. "today" for today forecast).
    """

    def next_info_update(self, config):
        """
        Return the next time the info should be updated after performance was
        played, or None if it should not be updated.

        Default implementation is to update info every hour.
        """
        if config is None:
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        next_hour = now + datetime.timedelta(seconds=3600)
        return next_hour

    @abstractmethod
    async def fetch_info_data(self, config):
        """
        Fetch the info data from whatever source, using config.
        """
        pass

    @abstractmethod
    def get_animation(self, info_data):
        """
        Return the new animation or None if none should be displayed.
        """
        pass

    @abstractmethod
    async def perform_additional(
        self, expiration_date, type, info_data, config
    ):
        """
        Perform whatever additional message, typically triggered from ASR
        or the website.
        """
        pass

    async def perform(self, expiration_date, type, config):
        # Always fetch info data.
        logging.info(f"fetch_info_data type = {type}")
        info_data = await self._do_fetch_info_data(config)
        info_animation = self.get_animation(info_data)
        service_name = self.__class__.__name__.lower()
        if info_animation != None:
            info_packet = (
                '{"type":"info","info_id":"'
                + service_name
                + '","animation":'
                + info_animation
                + "}\r\n"
            )
        else:
            info_packet = (
                '{"type":"info","info_id":"' + service_name + '"}\r\n'
            )
        self.writer.write(info_packet.encode("utf8"))
        if type != "info":
            await self.perform_additional(
                expiration_date, type, info_data, config
            )

    def compute_next(self, saved_date, saved_args, config, reason):
        logging.info(f"compute_next saved_date={saved_date}")
        now = datetime.datetime.now(datetime.timezone.utc)
        if saved_date is not None and saved_date < now:
            logging.info(f"compute_next saved_date < now")
            return saved_date, saved_args
        if reason == NabRecurrentService.Reason.BOOT:
            logging.info(f"compute_next reason == BOOT")
            return now, "info"
        if reason == NabRecurrentService.Reason.CONFIG_RELOADED:
            logging.info(f"compute_next reason == CONFIG_RELOADED")
            return now, "info"
        next_date = self.next_info_update(config)
        return next_date, "info"

    async def _do_fetch_info_data(self, config):
        """
        Invokes fetch_info_data, used by NabInfoCachedService subclass.
        """
        info_data = await self.fetch_info_data(config)
        return info_data


class NabInfoCachedService(NabInfoService, ABC):
    """
    Base class for an info service which additionally caches the remote info
    locally, to minimize delay for on-demand performances (voice, website).

    Info is cached for 1 hour.
    """

    def __init__(self):
        super().__init__()
        self.cached_info = None
        self.cached_info_config = None
        self.cached_info_expdate = None

    async def _do_fetch_info_data(self, config):
        """
        Fetch the info data from whatever source, using config, caching it
        locally.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        if (
            self.cached_info is not None
            and self.cached_info_config == config
            and self.cached_info_expdate is not None
            and self.cached_info_expdate > now
        ):
            return self.cached_info
        next_hour = now + datetime.timedelta(seconds=3600)
        new_info = await self.fetch_info_data(config)
        self.cached_info = new_info
        self.cached_info_config = config
        self.cached_info_expdate = next_hour
        return new_info
