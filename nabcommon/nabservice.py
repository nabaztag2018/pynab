import asyncio, os, json, getopt, signal
from abc import ABC, abstractmethod
from lockfile.pidlockfile import PIDLockFile
from lockfile import AlreadyLocked, LockFailed
from django.conf import settings
from django.apps import apps
from nabd import nabd

class NabService(ABC):
  def __init__(self):
    if not settings.configured:
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
    self.loop.call_soon_threadsafe(lambda : self.loop.create_task(self.reload_config()))

  @abstractmethod
  async def reload_config(self):
    """
    Reload configuration (on USR1 signal).
    """
    pass

  @abstractmethod
  async def process_nabd_packet(self, packet):
    pass

  async def client_loop(self):
    try:
      while self.running:
        line = await self.reader.readline()
        if line != b'' and line != b'\r\n':
          try:
            packet = json.loads(line)
            await self.process_nabd_packet(packet)
          except json.decoder.JSONDecodeError as e:
            print(f'Invalid JSON packet from nabd: {line}\n{str(e)}')
    except KeyboardInterrupt:
      pass
    finally:
      if self.running:
        self.loop.stop()

  def connect(self):
    loop = asyncio.get_event_loop()
    connection = asyncio.open_connection(host="127.0.0.1", port=nabd.Nabd.PORT_NUMBER)
    try:
      (reader, writer) = loop.run_until_complete(connection)
    except ConnectionRefusedError:
      print('Could not connect to server. Is nabd running?')
      exit(1)
    self.reader = reader
    self.writer = writer
    loop.create_task(self.client_loop())

  @abstractmethod
  def run(self):
    pass

  @classmethod
  def signal_daemon(cls):
    service_name = cls.__name__.lower()
    pidfilepath = f'/var/run/{service_name}.pid'
    try:
      with open(pidfilepath, 'r') as f:
        pidstr = f.read()
      os.kill(int(pidstr), signal.SIGUSR1)
    # Silently ignore the fact that the daemon is not running
    except OSError:
      pass
    except FileNotFoundError:
      pass

  @classmethod
  def main(cls, argv):
    service_name = cls.__name__.lower()
    pidfilepath = f'/var/run/{service_name}.pid'
    usage = f'{service_name} [options]\n' \
     + ' -h                   display this message\n' \
     + f' --pidfile=<pidfile>  define pidfile (default = {pidfilepath})\n'
    try:
      opts, args = getopt.getopt(argv,"h",["pidfile="])
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
      print(f'{service_name} already running? (pid={pidfile.read_pid()})')
      exit(1)
    except LockFailed:
      print(f'Cannot write pid file to {pidfilepath}, please fix permissions')
      exit(1)
