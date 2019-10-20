import asyncio
import os
import json
import getopt
import signal
import datetime
import sys
import time
from abc import ABC, abstractmethod
from lockfile.pidlockfile import PIDLockFile
from lockfile import AlreadyLocked, LockFailed
from django.conf import settings
from django.apps import apps
import logging
from nabcommon import nablogging


class NabService(ABC):
    PORT_NUMBER = 10543

    def __init__(self):
        if not settings.configured:
            from django.apps.config import AppConfig
            conf = {
                'INSTALLED_APPS': [
                    type(self).__name__.lower()
                ],
                'USE_TZ': True,
                'DATABASES': {
                    'default': {
                        'ENGINE': 'django.db.backends.postgresql',
                        'NAME': 'pynab',
                        'USER': 'pynab',
                        'PASSWORD': '',
                        'HOST': '',
                        'PORT': '',
                    }
                }
            }
            settings.configure(**conf)
            apps.populate(settings.INSTALLED_APPS)
        self.reader = None
        self.writer = None
        self.loop = None
        self.running = True
        signal.signal(signal.SIGUSR1, self.signal_handler)

    def signal_handler(self, sig, frame):
        self.loop.call_soon_threadsafe(lambda: self.loop.create_task(self.reload_config()))

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
            while self.running and not self.reader.at_eof():
                line = await self.reader.readline()
                if line != b'' and line != b'\r\n':
                    try:
                        packet = json.loads(line.decode('utf8'))
                        logging.debug('process nabd packet: {packet}'.format(packet=packet))
                        await self.process_nabd_packet(packet)
                    except json.decoder.JSONDecodeError as e:
                        logging.error('Invalid JSON packet from nabd: {line}\n{e}'.format(line=line, e=e))
            self.writer.close()
            await self.writer.wait_closed()
        except KeyboardInterrupt:
            pass
        finally:
            if self.running:
                self.loop.stop()

    MAX_RETRY = 10

    def connect(self):
        self.loop = asyncio.get_event_loop()
        self._do_connect(NabService.MAX_RETRY)
        self.loop.create_task(self.client_loop())

    def _do_connect(self, retry_count):
        connection = asyncio.open_connection(host="127.0.0.1", port=NabService.PORT_NUMBER)
        try:
            (reader, writer) = self.loop.run_until_complete(connection)
            self.reader = reader
            self.writer = writer
        except ConnectionRefusedError:
            if retry_count == 0:
                print('Could not connect to server. Is nabd running?')
                logging.critical('Could not connect to server. Is nabd running?')
                exit(1)
            time.sleep(1)
            self._do_connect(retry_count - 1)

    @abstractmethod
    def run(self):
        pass

    @classmethod
    def signal_daemon(cls):
        service_name = cls.__name__.lower()
        pidfilepath = '/var/run/{service_name}.pid'.format(service_name=service_name)
        try:
            with open(pidfilepath, 'r') as f:
                pidstr = f.read()
            os.kill(int(pidstr), signal.SIGUSR1)
        # Silently ignore the fact that the daemon is not running
        except OSError:
            pass

    @classmethod
    def main(cls, argv):
        service_name = cls.__name__.lower()
        nablogging.setup_logging(service_name)
        pidfilepath = '/var/run/{service_name}.pid'.format(service_name=service_name)
        usage = \
            '{service_name} [options]\n'.format(service_name=service_name) \
            + ' -h                   display this message\n' \
            + ' --pidfile=<pidfile>  define pidfile (default = {pidfilepath})\n'.format(pidfilepath=pidfilepath)
        try:
            opts, args = getopt.getopt(argv, "h", ["pidfile="])
        except getopt.GetoptError:
            print(usage)
            exit(2)
        for opt, arg in opts:
            if opt == '-h':
                print(usage)
                exit(0)
            elif opt == '--pidfile':
                pidfilepath = arg
        pidfile = PIDLockFile(pidfilepath, timeout=-1)
        try:
            with pidfile:
                service = cls()
                service.run()
        except AlreadyLocked:
            error_msg = '{service_name} already running? (pid={pid})'.format(service_name=service_name, pid=pidfile.read_pid())
            print(error_msg)
            logging.critical(error_msg)
            exit(1)
        except LockFailed:
            error_msg = 'Cannot write pid file to {pidfilepath}, please fix permissions'.format(pidfilepath=pidfilepath)
            print(error_msg)
            logging.critical(error_msg)
            exit(1)


class NabRecurrentService(NabService, ABC):
    """
    Common class for recurrent services
    Next performance time is saved in database.
    Reload configuration on USR1 signal.
    """
    def __init__(self):
        super().__init__()
        self._get_config()
        self.saved_freq_config = self.freq_config
        self.loop_cv = asyncio.Condition()

    @abstractmethod
    def get_config(self):
        """
        Return a tuple (next_date, next_args, freq_config) or (next_date, freq_config) from configuration.
        freq_config is any value sufficient to compute date and args of next performance.
        """
        pass

    @abstractmethod
    def update_next(self, next_date, next_args):
        """
        Write new next date and args to database.
        """
        pass

    @abstractmethod
    def compute_next(self, freq_config):
        """
        Compute next performance based on freq_config.
        Return None if no further performance should be scheduled.
        Otherwise, return tuple (next_date, next_args)
        """
        pass

    @abstractmethod
    def perform(self, date, args):
        """
        Perform the action.
        """
        pass

    async def reload_config(self):
        logging.info('reloading configuration')
        from django.core.cache import cache
        cache.clear()
        self._get_config()
        async with self.loop_cv:
            self.loop_cv.notify()

    async def service_loop(self):
        try:
            async with self.loop_cv:
                while self.running:
                    try:
                        now = datetime.datetime.now(datetime.timezone.utc)
                        next_date = self.next_date
                        next_args = self.next_args
                        if next_date is not None and next_date <= now:
                            self.perform(next_date + datetime.timedelta(minutes=1), next_args)
                            next_date = None
                            next_args = None
                        if self.saved_freq_config != self.freq_config or next_date is None:
                            next_tuple = self.compute_next(self.freq_config)
                            if next_tuple is None:
                                next_date = None
                                next_args = None
                            else:
                                (next_date, next_args) = next_tuple
                        if next_date != self.next_date or next_args != self.next_args:
                            self.next_date = next_date
                            self.next_args = next_args
                            self.update_next(next_date, next_args)
                        self.saved_freq_config = self.freq_config
                        if next_date is None:
                            sleep_amount = None
                        else:
                            sleep_amount = (next_date - now).total_seconds()
                        await asyncio.wait_for(self.loop_cv.wait(), sleep_amount)
                    except asyncio.TimeoutError:
                        pass
        except KeyboardInterrupt:
            pass
        finally:
            if self.running:
                asyncio.get_event_loop().stop()

    async def stop_service_loop(self):
        async with self.loop_cv:
            self.running = False    # signal to exit
            self.loop_cv.notify()

    def run(self):
        super().connect()
        service_task = self.loop.create_task(self.service_loop())
        try:
            self.loop.run_forever()
            if service_task.done():
                ex = service_task.exception()
                if ex:
                    raise ex
        except KeyboardInterrupt:
            pass
        finally:
            self.writer.close()
            self.loop.run_until_complete(self.stop_service_loop())
            tasks = asyncio.all_tasks(self.loop)
            for t in [t for t in tasks if not (t.done() or t.cancelled())]:
                self.loop.run_until_complete(t)      # give canceled tasks the last chance to run
            self.loop.close()

    def _get_config(self):
        config_tuple = self.get_config()
        if len(config_tuple) == 3:
            (self.next_date, self.next_args, self.freq_config) = config_tuple
        else:
            (self.next_date, self.freq_config) = config_tuple
            self.next_args = None


class NabRandomService(NabRecurrentService, ABC):
    """
    Common class for Tai Chi and Surprise.
    freq_config is an integer passed to compute_random_delta.
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

    def compute_next(self, frequency):
        next = self.do_compute_next(frequency)
        if next is None:
            return None
        return (next, self.next_args)
