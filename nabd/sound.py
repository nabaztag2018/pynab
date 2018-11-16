import abc
from .resources import Resources

class Sound(object, metaclass=abc.ABCMeta):
  """ Interface for sound """

  async def preload(self, audio_resource):
    # For now only consider local paths
    file = Resources.find('sounds', audio_resource)
    if file != None:
      return file.as_posix()
    return None

  async def play_list(self, filenames):
    self.stop()
    for filename in filenames:
      self.start(filename)
      await self.wait_until_done()

  async def start(self, audio_resource):
    preloaded = await self.preload(audio_resource)
    if preloaded != None:
      await self.start_preloaded(preloaded)

  async def start_preloaded(self, filename):
    """
    Start to play a given sound.
    Stop currently playing sound if any.
    """
    raise NotImplementedError( 'Should have implemented' )

  async def wait_until_done(self):
    """
    Wait until sound has been played.
    """
    raise NotImplementedError( 'Should have implemented' )

  async def stop(self):
    """
    Stop currently playing sound.
    """
    raise NotImplementedError( 'Should have implemented' )
