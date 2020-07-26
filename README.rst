========
Fabricio
========

Fabricio is a `Docker`_ deploy automation tool used along with the `Fabric`_.

.. _Fabric: http://www.fabfile.org
.. _Docker: https://www.docker.com

.. image:: https://travis-ci.org/renskiy/fabricio.svg?branch=master
    :target: https://travis-ci.org/renskiy/fabricio
.. image:: https://coveralls.io/repos/github/renskiy/fabricio/badge.svg?branch=master
    :target: https://coveralls.io/github/renskiy/fabricio?branch=master

Features
========

- build Docker images
- create containers and services from images with provided tags
- unlimited infrastructures
- Fabric's parallel execution mode compatibility
- rollback containers or services to previous version
- public and private Docker registries support
- deploy over SSH tunnel (e.g. access to image registry, proxy, etc.)
- migrations apply and rollback
- data backup and restore
- Docker services (Swarm mode)
- Docker stacks (Docker Compose 3.0+)
- Kubernetes configurations

See changelog_ for detailed info.

.. _changelog: https://github.com/renskiy/fabricio/blob/master/changelog.rst

Basic example
=============

The most basic :code:`fabfile.py` you can use with the Fabricio may look something like this:

.. code:: python

    from fabricio import docker, tasks
    
    app = tasks.DockerTasks(
        service=docker.Container(
            name='app',
            image='nginx:stable-alpine',
            options={
                'publish': '80:80',
            },
        ),
        hosts=['user@example.com'],
    )
    
Type :code:`fab --list` in your terminal to see available Fabric commands:

::

    Available commands:

        app.deploy  deploy service (prepare -> push -> backup -> pull -> migrate -> update)

Finally, to deploy such configuration you simply have to execute following bash command:

.. code:: bash

    fab app.deploy

See also Fabricio `examples and recipes`_.

.. _examples and recipes: https://github.com/renskiy/fabricio/tree/master/examples/

Requirements
============

Local
-----

- Python 2.7, 3.4*, 3.5*, 3.6*, 3.7*, 3.8*
- (optional) Docker 1.9+ for building Docker images

\* `Fabric3`_ is used for compatibility with Python 3.x

.. _Fabric3: https://github.com/mathiasertl/fabric/

Remote
------

- sshd
- Docker 1.9+
- Docker 1.12+ for using Docker services

Install
=======

.. code:: bash

    pip install fabricio
    
Note for macOS users
--------------------

Just use latest version of Python instead of one installed by default. The easiest way to install fresh version of Python is using `Homebrew`_:

.. code:: bash

    brew install python

.. _Homebrew: https://brew.sh

Contribute
==========

All proposals and improvements are welcomed through a `pull request`_ or issue_. Just make sure all tests are running fine.

.. _pull request: https://github.com/renskiy/fabricio/pulls
.. _issue: https://github.com/renskiy/fabricio/issues

Install test dependencies
-------------------------

.. code:: bash

    pip install ".[test]"

Running tests
-------------

.. code:: bash

    python -m unittest2 discover tests --verbose

Roles and infrastructures
=========================

You can define as many roles and infrastructures as you need. The following example shows 'production' and 'test' configurations for two-roles deploy configuration:

.. code:: python

    from fabric import colors, api as fab
    from fabricio import docker, tasks, infrastructure

    @infrastructure
    def testing():
        fab.env.roledefs.update(
            api=['user@testing.example.com'],
            web=['user@testing.example.com'],
        )

    @infrastructure(color=colors.red)
    def production():
        fab.env.roledefs.update(
            api=['user@api1.example.com', 'user@api2.example.com'],
            web=['user@web.example.com'],
        )

    web = tasks.DockerTasks(
        service=docker.Container(
            name='web',
            image='registry.example.com/web:latest',
            options={
                'publish': ['80:80', '443:443'],
                'volume': '/media:/media',
            },
        ),
        roles=['web'],
    )

    api = tasks.DockerTasks(
        service=docker.Container(
            name='api',
            image='registry.example.com/api:latest',
            options={
                'publish': '80:80',
            },
        ),
        roles=['api'],
    )

Here is the list of available commands:

::

    Available commands:

        production  select production infrastructure, 'production.confirm' skips confirmation dialog
        testing     select testing infrastructure, 'testing.confirm' skips confirmation dialog
        api.deploy  deploy service (prepare -> push -> backup -> pull -> migrate -> update)
        web.deploy  deploy service (prepare -> push -> backup -> pull -> migrate -> update)

'production' and 'testing' are available infrastructures here. To deploy to a particular infrastructure just provide it before any other Fabric command(s). For example:

.. code:: bash

    fab testing api.deploy web.deploy

See `Infrastructures and roles`_ example for more details.

.. _Infrastructures and roles: https://github.com/renskiy/fabricio/blob/master/examples/roles

Tags
====

Almost every Fabricio command takes optional argument 'tag' which means Docker image tag to use when deploying container or service. For instance, if you want to deploy specific version of your application you can do it as following:

.. code:: bash

    fab app.deploy:release-42

By default, value for tag is taken from Container/Service Image.

Also it is possible to completely (and partially) replace registry/account/name/tag/digest of image to deploy:

.. code:: bash

    fab app.deploy:registry.example.com/registry-account/app-image:release-42
    fab app.deploy:nginx@sha256:36b0181554913b471ae33546a9c19cc80e97f44ce5e7234995e307f14da57268

Rollback
========

To return container or service to a previous state execute this command:

.. code:: bash

    fab app.rollback

Idempotency
===========

Fabricio always tries to skip unnecessary container/service update. However, update can be forced by adding ``force=yes`` parameter:

.. code:: bash

    fab app.deploy:force=yes
    
Private Docker registry
=======================

It is often when production infrastructure has limited access to the Internet or your security policy does not allow using of public Docker image registries. In such case Fabricio offers ability to use private Docker registry which can be used also as an intermediate registry for the selected infrastructure. To use this option you have to have local Docker registry running within your LAN and also Docker client on your PC. If you have Docker installed you can run up Docker registry locally by executing following command:

.. code:: bash

    docker run --name registry --publish 5000:5000 --detach registry:2

When your local Docker registry is up and run you can provide custom ``registry`` which will be used as an intermediate Docker registry accessed via reverse SSH tunnel:

.. code:: python

    from fabricio import docker, tasks

    app = tasks.DockerTasks(
        service=docker.Container(
            name='app',
            image='nginx:stable-alpine',
            options={
                'publish': '80:80',
            },
        ),
        registry='localhost:5000',
        ssh_tunnel='5000:5000',
        hosts=['user@example.com'],
    )

See `Hello World`_ example for more details.

.. _Hello World: https://github.com/renskiy/fabricio/tree/master/examples/hello_world/#ssh-tunneling
    
Building Docker images
======================

Using Fabricio you can also build Docker images from local sources and deploy them to your servers. This example shows how this can be set up:

.. code:: python

    from fabricio import docker, tasks

    app = tasks.ImageBuildDockerTasks(
        service=docker.Container(
            name='app',
            image='registry.example.com/registry-account/app-image:latest-release',
        ),
        hosts=['user@example.com'],
        build_path='.',
    )

By executing command ``app.deploy`` Fabricio will try to build image using ``Dockerfile`` from the folder provided by ``build_path`` parameter. After that image will be pushed to the registry (registry.example.com in the example above). And deploy itself will start on the last step.

See `Building Docker images`_ example for more details.

.. _Building Docker images: https://github.com/renskiy/fabricio/blob/master/examples/build_image

Docker services
===============

Fabricio can deploy Docker services:

.. code:: python

    from fabricio import docker, tasks

    service = tasks.DockerTasks(
        service=docker.Service(
            name='my-service',
            image='nginx:stable',
            options={
                'publish': '8080:80',
                'replicas': 3,
            },
        ),
        hosts=['user@manager'],
    )

See `Docker services`_ example for more details.

.. _Docker services: https://github.com/renskiy/fabricio/blob/master/examples/service/swarm/

Docker stacks
=============

Docker stacks are also supported (available since Docker 1.13):

.. code:: python

    from fabricio import docker, tasks

    stack = tasks.DockerTasks(
        service=docker.Stack(
            name='my-docker-stack',
            options={
                'compose-file': 'my-docker-compose.yml',
            },
        ),
        hosts=['user@manager'],
    )

See `Docker stacks`_ example for more details.

.. _Docker stacks: https://github.com/renskiy/fabricio/blob/master/examples/service/stack/

Kubernetes configuration
========================

Kubernetes configuration can be deployed using following settings:

.. code:: python

    from fabricio import kubernetes, tasks

    k8s = tasks.DockerTasks(
        service=kubernetes.Configuration(
            name='my-k8s-configuration',
            options={
                'filename': 'configuration.yml',
            },
        ),
        hosts=['user@manager'],
    )

See `Kubernetes configuration`_ example for more details.

.. _Kubernetes configuration: https://github.com/renskiy/fabricio/blob/master/examples/service/kubernetes/
