import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ALLOWED_HOSTS = ['*']

SECRET_KEY = 'secret_key'

ROOT_URLCONF = 'urls'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/data/project.db',
    }
}

INSTALLED_APPS = [
    'app',
]
