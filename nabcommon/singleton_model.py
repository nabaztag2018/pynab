from django.db import models
from django.core.cache import cache

class SingletonModel(models.Model):
  """
  Singleton model for Django, used for service settings.
  
  Taken directly from https://steelkiwi.com/blog/practical-application-singleton-design-pattern/
  
  Copyright © 2017 SteelKiwi, http://steelkiwi.com

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
  """
  class Meta:
    abstract = True

  def set_cache(self):
    cache.set(self.__class__.cache_key(), self)

  def save(self, *args, **kwargs):
    self.pk = 1
    super(SingletonModel, self).save(*args, **kwargs)
    self.set_cache()

  def delete(self, *args, **kwargs):
    pass

  @classmethod
  def cache_key(cls):
    return cls.__module__ + '.' + cls.__name__

  @classmethod
  def load(cls):
    if cache.get(cls.cache_key()) is None:
      obj, created = cls.objects.get_or_create(pk=1)
      if not created:
        obj.set_cache()
    return cache.get(cls.cache_key())

  @classmethod
  def reset_cache(cls):
    """ Reset cache, used for tests """
    cache.delete(cls.cache_key())

class UncachableSingletonModel(SingletonModel):
  class Meta:
    abstract = True

  def set_cache(self):
    pass

  def save(self, *args, **kwargs):
    self.pk = 1
    super(SingletonModel, self).save(*args, **kwargs)

  @classmethod
  def load(cls):
    obj, created = cls.objects.get_or_create(pk=1)
    return obj

  @classmethod
  def reset_cache(cls):
    pass
