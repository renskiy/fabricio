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
- tasks groups
- migrations apply and rollback
- data backup and restore
- DB master-slave configurations support
- (**NEW**) Docker Swarm mode (Docker 1.12+)

See changelog_ for detailed info.

.. _changelog: changelog.rst

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
                'ports': '80:80',
            },
        ),
        hosts=['user@example.com'],
    )
    
Type :code:`fab --list` in your terminal to see available Fabric commands:

::

    Available commands:

        nginx           backup -> pull -> migrate -> update
        nginx.deploy    backup -> pull -> migrate -> update
        nginx.pull      pull Docker image from registry
        nginx.rollback  rollback service to a previous version
        nginx.update    update service to a new version

Finally, to deploy such configuration you simply have to execute following bash command:

.. code:: bash

    fab nginx

To display detailed info about command (including available options) use following command: ``fab --display <command>``.

See also Fabricio `examples and recipes`_.

.. _examples and recipes: examples/

Requirements
============

Local
-----

- Python 2.6 or 2.7
- `Fabric`_ 1.x
- (optional) Docker 1.9+ for building Docker images

Remote
------

- sshd
- Docker 1.9+
- (optional) Docker 1.12+ for using Docker in Swarm mode

Install
=======

.. code:: bash

    pip install --upgrade fabricio
    
*For system-wide installation macOS users should explicitly provide version of the 'six' package installed on their system. For example:*

.. code:: bash

    sudo pip install --upgrade fabricio six==1.4.1

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
                'ports': ['80:80', '443:443'],
                'volumes': '/etc/cert:/etc/cert:ro',
            },
        ),
        roles=['balancer'],
    )

    web = tasks.DockerTasks(
        service=docker.Container(
            name='web',
            image='registry.example.com/nginx:web',
            options={
                'ports': '80:80',
                'volumes': '/media:/media',
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
        balancer            backup -> pull -> migrate -> update
        balancer.deploy     backup -> pull -> migrate -> update
        balancer.pull       pull Docker image from registry
        balancer.rollback   rollback service to a previous version
        balancer.update     update service to a new version
        web                 backup -> pull -> migrate -> update
        web.deploy          backup -> pull -> migrate -> update
        web.pull            pull Docker image from registry
        web.rollback        rollback service to a previous version
        web.update          update service to a new version
        
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
                'ports': '80:80',
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

    nginx.prepare   prepare Docker image
    nginx.push      push Docker image to registry
    
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
