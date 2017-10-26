========
Fabricio
========

Fabricio is a `Docker`_ deploy automation tool used along with the `Fabric`_.

.. _Fabric: http://www.fabfile.org
.. _Docker: https://www.docker.com
.. _swarm mode: https://docs.docker.com/engine/swarm/

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
- tasks groups
- migrations apply and rollback
- data backup and restore
- DB master-slave configurations support
- (**NEW**) Docker Swarm mode (Docker 1.12+)

See changelog_ for detailed info.

.. _changelog: https://github.com/renskiy/fabricio/blob/master/changelog.rst

Basic example
=============

The most basic :code:`fabfile.py` you can use with the Fabricio is something like this:

.. code:: python

    from fabricio import docker, tasks
    
    
    nginx = tasks.DockerTasks(
        service=docker.Container(
            name='nginx',
            image='nginx:stable',
            options={
                'publish': '80:80',
            },
        ),
        hosts=['user@example.com'],
    )
    
Type :code:`fab --list` in your terminal to see available Fabric commands:

::

    Available commands:

        nginx           full service deploy (prepare -> push -> upgrade)
        nginx.deploy    full service deploy (prepare -> push -> upgrade)
        nginx.rollback  rollback service to a previous version (migrate-back -> revert)
        nginx.upgrade   upgrade service to a new version (backup -> pull -> migrate -> update)

Finally, to deploy such configuration you simply have to execute following bash command:

.. code:: bash

    fab nginx

To display detailed info about command (including available options) use following command: ``fab --display <command>``.

See also Fabricio `examples and recipes`_.

.. _examples and recipes: https://github.com/renskiy/fabricio/tree/master/examples

Requirements
============

Local
-----

- Python 2.6+ or Python 3.4+*
- (optional) Docker 1.9+ for building Docker images

\* `Fabric3`_ is used for compatibility with Python 3

.. _Fabric3: https://github.com/mathiasertl/fabric/

Remote
------

- sshd
- Docker 1.9+
- (optional) Docker 1.12+ for using Docker in Swarm mode

Install
=======

.. code:: bash

    pip install fabricio
    
Note for macOS users
--------------------

Because of Python 2 on macOS marked as system component you can't upgrade its modules which are trying to be upgraded during the Fabricio install (e.g. ``six`` and ``setuptools``). Instead, you can try to install last version of Python 2 using `Homebrew`_:

.. code:: bash

    brew install python2

and then:

.. code:: bash

    pip2 install fabricio

.. _Homebrew: https://brew.sh

Roles and infrastructures
=========================

You can define as many roles and infrastructures as you need. The following example shows 'production' and 'staging' configurations for two-roles deploy configuration:

.. code:: python

    from fabric import colors, api as fab
    from fabricio import docker, tasks


    @tasks.infrastructure
    def staging():
        fab.env.roledefs.update(
            balancer=['user@staging.example.com'],
            web=['user@staging.example.com'],
        )


    @tasks.infrastructure(color=colors.red)
    def production():
        fab.env.roledefs.update(
            balancer=['user@balancer.example.com'],
            web=['user@web1.example.com', 'user@web2.example.com'],
        )

    balancer = tasks.DockerTasks(
        service=docker.Container(
            name='balancer',
            image='registry.example.com/nginx:balancer',
            options={
                'publish': ['80:80', '443:443'],
                'volume': '/etc/cert:/etc/cert:ro',
            },
        ),
        roles=['balancer'],
    )

    web = tasks.DockerTasks(
        service=docker.Container(
            name='web',
            image='registry.example.com/nginx:web',
            options={
                'publish': '80:80',
                'volume': '/media:/media',
            },
        ),
        roles=['web'],
    )

Here is the list of available commands:

::

    Available commands:

        production          select production infrastructure to run task(s) on
        production.confirm  automatically confirm production infrastructure selection
        staging             select staging infrastructure to run task(s) on
        staging.confirm     automatically confirm staging infrastructure selection
        balancer            full service deploy (prepare -> push -> upgrade)
        balancer.deploy     full service deploy (prepare -> push -> upgrade)
        balancer.rollback   rollback service to a previous version (migrate-back -> revert)
        balancer.upgrade    upgrade service to a new version (backup -> pull -> migrate -> update)
        web                 full service deploy (prepare -> push -> upgrade)
        web.deploy          full service deploy (prepare -> push -> upgrade)
        web.rollback        rollback service to a previous version (migrate-back -> revert)
        web.upgrade         upgrade service to a new version (backup -> pull -> migrate -> update)

'production' and 'staging' are available infrastructures here. To deploy to a particular infrastructure just provide it before any other Fabric command. For example:

.. code:: bash

    fab staging balancer web

Tags
====

Almost every Fabricio command takes optional argument 'tag' which means Docker image tag to use when deploying container or service. For instance, if you want to deploy specific version of your application you can do it as following:

.. code:: bash

    fab app.deploy:v1.2

By default, value for tag is taken from Container/Service Image.

Rollback
========

To return container or service to a previous version execute command :code:`fab app.rollback`.

Forced update
=============

.. code:: bash

    fab app.update:force=yes
    
``force=yes`` is used to force container or service update.

Private Docker registry
=======================

It is often when production infrastructure has limited access to the Internet or your security policy does not allow using of public Docker image registries. In such case Fabricio offers ability to use private Docker registry which can be used also as an intermediate registry for the selected infrastructure. To use this option you have to have local Docker registry running within your LAN and also Docker client on your PC. If you have Docker installed you can run up Docker registry locally by executing following command:

.. code:: bash

    docker run --name registry --publish 5000:5000 --detach registry:2

When your local Docker registry is up and run you can provide custom ``registry`` which will be used as an intermediate Docker registry accessed via reverse SSH tunnel:

.. code:: python

    from fabricio import docker, tasks

    nginx = tasks.DockerTasks(
        service=docker.Container(
            name='nginx',
            image='nginx:stable',
            options={
                'publish': '80:80',
            },
        ),
        registry='localhost:5000',
        ssh_tunnel_port=5000,
        hosts=['user@example.com'],
    )

*Note, that you can provide custom registry and/or account within 'image' parameter like this:*

.. code:: python

    image='custom-registry.example.com/user/image:tag'

List of commands in this case updated with additional two commands:

::

    nginx.prepare   build Docker image
    nginx.push      push built Docker image to the registry
    
The first one pulls Image from the original registry and the second pushes it to the local registry which is used as main registry for all configuration's infrastructures.

Building Docker images
======================

Using Fabricio you can also build Docker images from local sources and deploy them to your servers. This example shows how this can be set up:

.. code:: python

    from fabricio import docker, tasks

    app = tasks.ImageBuildDockerTasks(
        service=docker.Container(
            name='app',
            image='your_docker_hub_account/app',
        ),
        hosts=['user@example.com'],
        build_path='src',
    )

Commands list for :code:`ImageBuildDockerTasks` is same as for :code:`DockerTasks` with provided custom registry. The only difference is that 'prepare' builds image instead of pulling it from the original registry.

And of course, you can use your own private Docker registry:

.. code:: python

    from fabricio import docker, tasks

    app = tasks.ImageBuildDockerTasks(
        service=docker.Container(
            name='app',
            image='app',
        ),
        registry='registry.your_company.com',
        hosts=['user@example.com'],
        build_path='src',
    )

Docker services (swarm mode)
============================

Fabricio also can work with Docker services AKA (Also Known As) `swarm mode`_ (Docker 1.12+):

.. code:: python

    from fabricio import docker, tasks

    nginx = tasks.DockerTasks(
        service=docker.Service(
            name='nginx',
            image='nginx:stable',
            options={
                'publish': '8080:80',
                'replicas': 3,
            },
        ),
        hosts=['user@manager'],
    )
