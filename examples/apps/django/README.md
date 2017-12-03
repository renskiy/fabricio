# Fabricio: Django

This example shows how to deploy [Django](https://www.djangoproject.com) configuration consisting of a single container based on custom image which automatically built from provided [Dockerfile](Dockerfile).

## Requirements

* Fabricio 0.4.1 or greater
* [Vagrant](https://www.vagrantup.com)
* One from the [list of Vagrant supported providers](https://www.vagrantup.com/docs/providers/) (this example was tested with [VirtualBox](https://www.virtualbox.org/))
* [Docker](https://www.docker.com/products/overview) for Linux/Mac/Windows
* Docker registry which runs locally on 5000 port, this can be reached out by executing following docker command: `docker run --name registry --publish 5000:5000 --detach registry:2`

## Files

* __project/__, folder with Django application
* __Dockerfile__, used for building image
* __fabfile.py__, Fabricio configuration
* __README.md__, this file
* __Vagrantfile__, Vagrant config

## Virtual Machine creation

Run `vagrant up` and wait until VM will be created.

## List of available commands

    fab --list

## Deploy

    fab django
    
## Rollback

Copy `0003_copy_this_to_parent_folder.py` migration file from `project/app/migrations/new/` directory to the parent one (`project/app/migrations/`) and then make deploy again:

    fab django
    
This will apply new migration. After that run 'rollback' command which should remove newly applied migration:

    fab django.rollback
    
## Customization

See also "Hello, World" [Customization](../../hello_world/#customization) section.

### DJANGO_SETTINGS_MODULE customization

You can provide custom settings to each infrastructure you have by providing callable DJANGO_SETTINGS_MODULE `env` option:

```python
from fabric import api as fab
from fabricio import tasks
from fabricio.apps.python.django import DjangoContainer

def django_settings(**additional_variables):
    def _settings(
        container,  # type DjangoContainer
    ):
        # select settings module depending on infrastructure name
        # (see 'Infrastructures and roles' example)
        settings = ('settings', fab.env.infrastructure)
        env = ['DJANGO_SETTINGS_MODULE=%s' % '.'.join(settings)]
        env.extend(map('='.join, additional_variables.items()))
        return env
    return _settings

django = tasks.ImageBuildDockerTasks(
    service=DjangoContainer(
        name='django',
        image='django',
        options={
            'publish': '8000:8000',
            'stop-signal': 'INT',
            'volume': '/data/django:/data',
            'env': django_settings(
                FOO='foo',
            ),
        },
    ),
    # ...
)
```

### DjangoService

To use Django as Docker service (such as described in [Docker services](../../service/swarm/) example) one can use `DjangoService` instance:

```python
from fabricio import tasks
from fabricio.apps.python.django import DjangoService

django = tasks.ImageBuildDockerTasks(
    service=DjangoService(
        name='django',
        image='django',
        options={
            'publish': '8000:8000',
            'stop-signal': 'INT',
            'env': 'DJANGO_SETTINGS_MODULE=settings',
        },
    ),
    # ...
)
```

### DjangoStack

Also, Django can be a part of Docker stack (see [Docker stacks](../../service/stack/) example):

```python
from fabricio import tasks
from fabricio.apps.python.django import DjangoStack

django = tasks.ImageBuildDockerTasks(
    service=DjangoStack(
        # stack name
        name='django-stack',
        
        # image tag which will be built and used to apply migrations on
        # (all other stack images must be ready to the moment of stack deploy)
        image='django-app',
        
        # safe options are options passing to container
        # that does 'migrate' (or 'migrate-back') operation
        safe_options={
            'stop-signal': 'INT',
            'env': 'DJANGO_SETTINGS_MODULE=settings',
        },
    ),
    # ...
)
```

## Issues

* If you see warnings in `Vagrant` logs about Guest Extensions version is not match VirtualBox version try to install `vagrant-vbguest` plugin that automatically installs Guest Extensions of version which corresponds to your version of VirtualBox: `vagrant plugin install vagrant-vbguest`
* Windows users may fall into trouble with `VirtualBox` and `Hyper-V`, the latter is used by "native" Docker for Windows. Try to disable Hyper-V and use [Docker Toolbox](https://www.docker.com/products/docker-toolbox) instead in such case
