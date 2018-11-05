import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALLED_APPS = [
    'nabclockd',
]
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'pynab',                      
        'USER': 'pynab',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}
SECRET_KEY = '+m)qk@&t%tlqj@o$jo$&egt34r7yu0fq4v!0o82&b9+b51ppyy'
