import abc
from .resources import Resources

class Sound(object, metaclass=abc.ABCMeta):
    """ Interface for sound """

    async def preload(self, audio_resource):
        # For now only consider local paths
        file = Resources.find('sounds', audio_resource)
        if file != None:
            return file.as_posix()
        print('Warning : could not find resource {r}'.format(r = audio_resource))
        return None

    async def play_list(self, filenames, preloaded):
        preloaded_list = []
        if preloaded:
            preloaded_list = filenames
        else:
            for filename in filenames:
                preloaded_file = await self.preload(filename)
                if preloaded_file != None:
                    preloaded_list.append(preloaded_file)
        await self.stop_playing()
        for filename in preloaded_list:
            await self.start_playing_preloaded(filename)
            await self.wait_until_done()

    async def start_playing(self, audio_resource):
        preloaded = await self.preload(audio_resource)
        if preloaded != None:
            await self.start_playing_preloaded(preloaded)

    async def start_playing_preloaded(self, filename):
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

    async def stop_playing(self):
        """
        Stop currently playing sound.
        """
        raise NotImplementedError( 'Should have implemented' )

    async def start_recording(self, stream_cb):
        """
        Start recording sound.
        Invokes stream_cb repeatedly with recorded samples.
        """
        raise NotImplementedError( 'Should have implemented' )

    async def stop_recording(self):
        """
        Stop recording sound.
        Invokes stream_cb with finalize set to true.
        """
        raise NotImplementedError( 'Should have implemented' )
