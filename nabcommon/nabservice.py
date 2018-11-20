import asyncio, os, json, getopt, signal, datetime, sys
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

  async def process_nabd_packet(self, packet):
    pass

  async def client_loop(self):
    try:
      while self.running:
        line = await self.reader.readline()
        if line != b'' and line != b'\r\n':
          try:
            packet = json.loads(line.decode('utf8'))
            await self.process_nabd_packet(packet)
          except json.decoder.JSONDecodeError as e:
            print('Invalid JSON packet from nabd: {line}\n{e}'.format(line=line, e=e))
    except KeyboardInterrupt:
      pass
    finally:
      if self.running:
        self.loop.stop()

  def connect(self):
    self.loop = asyncio.get_event_loop()
    connection = asyncio.open_connection(host="127.0.0.1", port=nabd.Nabd.PORT_NUMBER)
    try:
      (reader, writer) = self.loop.run_until_complete(connection)
    except ConnectionRefusedError:
      print('Could not connect to server. Is nabd running?')
      exit(1)
    self.reader = reader
    self.writer = writer
    self.loop.create_task(self.client_loop())

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
    except FileNotFoundError:
      pass

  @classmethod
  def main(cls, argv):
    service_name = cls.__name__.lower()
    pidfilepath = '/var/run/{service_name}.pid'.format(service_name=service_name)
    usage = '{service_name} [options]\n'.format(service_name=service_name) \
     + ' -h                   display this message\n' \
     + ' --pidfile=<pidfile>  define pidfile (default = {pidfilepath})\n'.format(pidfilepath=pidfilepath)
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
      print('{service_name} already running? (pid={pid})'.format(service_name=service_name, pid=pidfile.read_pid()))
      exit(1)
    except LockFailed:
      print('Cannot write pid file to {pidfilepath}, please fix permissions'.format(pidfilepath=pidfilepath))
      exit(1)

class NabRandomService(NabService, ABC):
  """
  Common class for Tai Chi and Surprise.
  Next performance time is defined in database.
  Reload configuration on USR1 signal.
  """
  def __init__(self):
    super().__init__()
    (self.next, self.frequency) = self.get_config()
    self.saved_frequency = self.frequency
    self.loop_cv = asyncio.Condition()

  @abstractmethod
  def get_config(self):
    """
    Return a tuple (frequency, next) from configuration.
    """
    pass

  @abstractmethod
  def update_next(self, next):
    """
    Write new next date to database.
    """
    pass

  @abstractmethod
  def perform(self, expiration):
    """
    Perform the random action.
    """
    pass

  @abstractmethod
  def compute_random_delta(self, frequency):
    """
    Return the delta (in seconds) with the next event based on frequency
    """
    pass

  async def reload_config(self):
    from django.core.cache import cache
    cache.clear()
    (self.next, self.frequency) = self.get_config()
    async with self.loop_cv:
      self.loop_cv.notify()

  async def service_loop(self):
    try:
      async with self.loop_cv:
        while self.running:
          try:
            now = datetime.datetime.now(datetime.timezone.utc)
            next = self.next
            if next != None and next <= now:
              self.perform(next + datetime.timedelta(minutes=1))
              next = None
            if self.saved_frequency != self.frequency or next == None:
              next = self.compute_next(self.frequency)
            if next != self.next:
              self.next = next
              self.update_next(next)
            self.saved_frequency = self.frequency
            if next == None:
              sleep_amount = None
            else:
              sleep_amount = (next - now).total_seconds()
            await asyncio.wait_for(self.loop_cv.wait(), sleep_amount)
          except asyncio.TimeoutError:
            pass
    except KeyboardInterrupt:
      pass
    finally:
      if self.running:
        asyncio.get_event_loop().stop()

  def compute_next(self, frequency):
    if frequency == 0:
      return None
    now = datetime.datetime.now(datetime.timezone.utc)
    next_delta = self.compute_random_delta(frequency)
    return now + datetime.timedelta(seconds = next_delta)

  async def stop_service_loop(self):
    async with self.loop_cv:
      self.running = False  # signal to exit
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
      if sys.version_info >= (3,7):
        tasks = asyncio.all_tasks(self.loop)
      else:
        tasks = asyncio.Task.all_tasks(self.loop)
      for t in [t for t in tasks if not (t.done() or t.cancelled())]:
        self.loop.run_until_complete(t)    # give canceled tasks the last chance to run
      self.loop.close()
