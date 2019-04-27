import struct
import numpy as np
import traceback
from concurrent.futures import ThreadPoolExecutor
from kaldiasr.nnet3 import KaldiNNet3OnlineModel, KaldiNNet3OnlineDecoder

class ASR:
  """
  Class handling automatic speech recognition.
  """
  MODELS = {
    'en_US': '/opt/kaldi/model/kaldi-generic-en-tdnn_250-r20190227'
  }
  DEFAULT_LANGUAGE = 'en_US'
  
  def __init__(self, language):
    self.executor = ThreadPoolExecutor(max_workers=1)
    self.executor.submit(lambda l=language: self._load_model(l))

  def _load_model(self, language):
    if language in ASR.MODELS:
      path = ASR.MODELS[language]
    else:
      path = ASR.MODELS[ASR.DEFAULT_LANGUAGE]
    self.model = KaldiNNet3OnlineModel(path)
    self.decoder = KaldiNNet3OnlineDecoder(self.model)

  def decode_chunk(self, samples, finalize):
    self.executor.submit(lambda s=samples, f=finalize: self._decode_chunk(s, f))

  def _decode_chunk(self, frames, finalize):
    nframes = len(frames) / 2
    samples = struct.unpack_from('<%dh' % nframes, frames)
    self.decoder.decode(16000, np.array(samples, dtype=np.float32), finalize)

  async def get_decoded_string(self, sync):
    if sync:
      future = self.executor.submit(lambda : self._get_decoded_string())
      return future.result()
    else:
      # not sure we could do that
      s, l = self.decoder.get_decoded_string()
      return s

  def _get_decoded_string(self):
    s, l = self.decoder.get_decoded_string()
    print("_get_decoded_string s = %s, l = %f" % (s, l))
    return s
