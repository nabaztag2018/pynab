from django.db import models
from asgiref.sync import sync_to_async


class SingletonModel(models.Model):
    """
    Singleton model for Django, used for service settings.

    Taken directly from
    https://steelkiwi.com/blog/practical-application-singleton-design-pattern/

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

    def save(self, *args, **kwargs):
        self.pk = 1
        super(SingletonModel, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    # asyncio-compatible versions, using sync_to_async
    @classmethod
    async def load_async(cls):
        return await sync_to_async(cls.load, thread_sensitive=True)()

    async def save_async(self, *args, **kwargs):
        return await sync_to_async(self.save, thread_sensitive=True)(
            *args, **kwargs
        )
