========
Fabricio
========

Fabricio is a Docker deploy automation tool used along with the `Fabric`_.

.. _Fabric: http://www.fabfile.org

.. image:: https://travis-ci.org/renskiy/fabricio.svg?branch=master
    :target: https://travis-ci.org/renskiy/fabricio
.. image:: https://coveralls.io/repos/github/renskiy/fabricio/badge.svg?branch=master
    :target: https://coveralls.io/github/renskiy/fabricio?branch=master

Features
========

- build Docker images
- create containers from images with provided tags
- unlimited infrastructures
- Fabric's parallel execution mode compatibility
- rollback containers to previous version
- public and private Docker registries support
- tasks groups
- migrations apply and rollback
- data backup and restore

See changelog_ for detailed info.

.. _changelog: changelog.rst

Basic example
=============

The most basic :code:`fabfile.py` you can use with the Fabricio is something like this:

.. code:: python

    from fabricio import docker, tasks
    
    
    class NginxContainer(docker.Container):
    
        image = docker.Image('nginx:stable')
        
        ports = '80:80'
    
    nginx = tasks.DockerTasks(
        container=NginxContainer('nginx'),
        hosts=['user@example.com'],
    )
    
Type :code:`fab --list` in your terminal to see available Fabric commands:

::

    Available commands:

        nginx           backup -> pull -> migrate -> update
        nginx.deploy    backup -> pull -> migrate -> update
        nginx.pull      pull Docker image from registry
        nginx.rollback  rollback container to previous version
        nginx.update    start new Docker container if necessary

Finally, to deploy such configuration you simply have to execute following bash command:

.. code:: bash

    fab nginx

To display detailed info about command (including available options) use following command: ``fab --display <command>``.

Install
=======

.. code:: bash

    pip install --upgrade fabricio

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
    
    
    @tasks.infrastructure
    def production():
        fab.env.roledefs.update(
            balancer=['user@balancer.example.com'],
            web=['user@web1.example.com', 'user@web2.example.com'],
        )
    
    
    class BalancerContainer(docker.Container):
    
        image = docker.Image('registry.example.com/nginx:balancer')
    
        ports = ['80:80', '443:443']
    
        volumes = '/etc/cert:/etc/cert:ro'
    
    
    class WebContainer(docker.Container):
    
        image = docker.Image('registry.example.com/nginx:cdn')
    
        ports = '80:80'
    
        volumes = '/media:/media'
    
    balancer = tasks.DockerTasks(
        container=BalancerContainer('balancer'),
        roles=['balancer'],
    )
    
    web = tasks.DockerTasks(
        container=BalancerContainer('web'),
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
        balancer.rollback   rollback container to previous version
        balancer.update     start new Docker container if necessary
        web                 backup -> pull -> migrate -> update
        web.deploy          backup -> pull -> migrate -> update
        web.pull            pull Docker image from registry
        web.rollback        rollback container to previous version
        web.update          start new Docker container if necessary
        
'production' and 'staging' are available infrastructures here. To deploy to a particular infrastructure just provide it before any other Fabric command. For example:

.. code:: bash

    fab staging balancer web

Tags
====

Almost every Fabricio command takes optional argument 'tag' which means Docker image tag to use when deploying container. For instance, if you want to deploy specific version of your application you can do it as following:

.. code:: bash

    fab app.deploy:v1.2

By default, value for tag is taken from Container's Image.

Rollback
========

To return container to previous version execute command :code:`fab app.rollback`.

Forced update
=============

.. code:: bash

    fab app.update:force=yes
    
Forced update forces creation of new container.

Local Docker registry
=====================

It is often when production infrastructure has limited access to the Internet. In such case Fabricio offers ability to use local Docker registry which can be used as an intermediate registry for the selected infrastructure. To use this option you have to have local Docker registry running within your LAN and also Docker client on your work PC. You can up your own Docker registry by executing following command on the PC with Docker installed:

.. code:: bash

    docker run --name registry --publish 5000:5000 --detach --restart always registry:2

When your local Docker registry is up and run you can use special tasks class to bypass infrastructure network limitations:

.. code:: python

    from fabricio import docker, tasks
    
    
    class NginxContainer(docker.Container):
    
        image = docker.Image('nginx:stable')
    
        ports = '80:80'
    
    nginx = tasks.PullDockerTasks(
        container=NginxContainer('nginx'),
        hosts=['user@example.com'],
    )

List of commands in this case updated with additional two commands:

::

    nginx.prepare   prepare Docker image
    nginx.push      push Docker image to registry
    
The first one pulls Image from the original registry and the second pushes it to the local registry which is used as main registry for all configuration's infrastructures.

Building Docker images
======================

Using local Docker registry you can also build Docker images from local sources. This example shows how this can be set up:

.. code:: python

    from fabricio import docker, tasks
    
    
    class AppContainer(docker.Container):
    
        image = docker.Image('app')
    
    app = tasks.BuildDockerTasks(
        container=AppContainer('app'),
        hosts=['user@example.com'],
        build_path='src',
    )

Commands list for :code:`BuildDockerTasks` is same as for :code:`PullDockerTasks`. The only difference is that 'prepare' builds image instead of pulling it from the original registry.
