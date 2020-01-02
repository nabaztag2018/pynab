import os
import random
from nabweb import settings
from pathlib import Path
import logging


class Resources(object):
    @staticmethod
    async def find(type, resources):
        """
        Find a resource from its type and its name.
        Return the first found resource, resources being delimited by
        semi-colons.
        Perform localization and random lookups with specific tag.
        Files are first searched in <app>/<type>/<locale>/ then <app>/<type>/
        Random lookup is performed when component is * or *.suffix
        """
        for filename in resources.split(";"):
            path0 = Path(resources)
            if path0.is_absolute():
                if path0.is_file():
                    return path0  # Already found
                raise ValueError(
                    f"find_resource expects a relative path, got {filename}"
                )
            if "/" in type:
                raise ValueError(
                    f"find_resource expects a directory name for type, "
                    f"got {type}"
                )
            is_random = path0.name.startswith("*")
            if is_random:
                result = await Resources._find_random(
                    type, path0.parent.as_posix(), path0.name
                )
            else:
                result = await Resources._find_file(type, filename)
            if result is not None:
                return result
        return None

    @staticmethod
    async def _find_file(type, filename):
        from .i18n import get_locale
        logging.debug(f"type {type}")
        logging.debug(f"filename {filename}")


        basepath = Path(settings.BASE_DIR)
        locale = await get_locale()
        
            #choosing a random locale among the locale available for this service
        if (type == 'sounds') and (locale == '*'):        
            first_parent = filename.split('/')[0]  
            logging.debug(f"first_parent {first_parent}")

            path_locales_directory = basepath.joinpath(first_parent, type)
            list_of_locales = []

            for item in os.listdir(path_locales_directory):
                if (item[2] =='_'):
                    list_of_locales.append(item)
            if list_of_locales != []:
                new_locale = random.choice(list_of_locales) 
                logging.debug(f"polyglotte mode - new_locale {new_locale}")   
                locale=new_locale                            
        
        for app in os.listdir(basepath):
            if not os.path.isdir(app):
                continue
            for path in [
                basepath.joinpath(app, type, locale, filename),
                basepath.joinpath(app, type, filename),
            ]:
                if path.is_file():
                    return path
        return None

    @staticmethod
    async def _find_random(type, parent, pattern):
        
        from .i18n import get_locale
        
        logging.debug(f"type {type}")
        logging.debug(f"parent {parent}")
        logging.debug(f"pattern {pattern}")
        
        head_tail = os.path.split(parent)
        if (head_tail[0] == ''):
            first_parent = head_tail[1]
        else:
            first_parent = head_tail[0]     
        

        basepath = Path(settings.BASE_DIR)
        logging.debug(basepath)
        locale = await get_locale()
        logging.debug(f"locale {locale}")


        if (type == 'sounds') and (locale == '*'):        
            #choosing a random locale among the locale available for this service
            path_locales_directory = basepath.joinpath(first_parent, type)
            list_of_locales = []

            for item in os.listdir(path_locales_directory):
                if (item[2] =='_'):
                    list_of_locales.append(item)
            if list_of_locales != []:
                new_locale = random.choice(list_of_locales) 
                logging.debug(f"polyglotte mode - new_locale {new_locale}")   
                locale=new_locale                            
        
        for app in os.listdir(basepath):
            if not os.path.isdir(app):
                continue
            for path in [
                basepath.joinpath(app, type, locale, parent),
                basepath.joinpath(app, type, parent),
            ]:
                if path.is_dir():
                    list = path.glob(pattern)
                    if list != []:
                        return random.choice(sorted(list))
        return None
