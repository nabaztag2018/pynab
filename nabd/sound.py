import abc
from .resources import Resources


class Sound(object, metaclass=abc.ABCMeta):
    """ Interface for sound """

    async def preload(self, audio_resource):
        # For now only consider local paths
        file = await Resources.find("sounds", audio_resource)
        if file is not None:
            return file.as_posix()
        print(f"Warning : could not find resource {audio_resource}")
        return None

    async def play_list(self, filenames, preloaded, event=None):
        preloaded_list = []
        if preloaded:
            preloaded_list = filenames
        else:
            for filename in filenames:
                preloaded_file = await self.preload(filename)
                if preloaded_file is not None:
                    preloaded_list.append(preloaded_file)
        await self.stop_playing()
        for filename in preloaded_list:
            await self.start_playing_preloaded(filename)
            await self.wait_until_done(event)

    async def start_playing(self, audio_resource):
        preloaded = await self.preload(audio_resource)
        if preloaded is not None:
            await self.start_playing_preloaded(preloaded)

    @abc.abstractmethod
    async def start_playing_preloaded(self, filename):
        """
        Start to play a given sound.
        Stop currently playing sound if any.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def wait_until_done(self, event=None):
        """
        Wait until sound has been played or event is fired.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def stop_playing(self):
        """
        Stop currently playing sound.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def start_recording(self, stream_cb):
        """
        Start recording sound.
        Invokes stream_cb repeatedly with recorded samples.
        """
        raise NotImplementedError("Should have implemented")

    @abc.abstractmethod
    async def stop_recording(self):
        """
        Stop recording sound.
        Invokes stream_cb with finalize set to true.
        """
        raise NotImplementedError("Should have implemented")
