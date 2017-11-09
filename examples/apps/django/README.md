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

See also "Hello, World" [Customization](../hello_world/#customization) section.

## Issues

* If you see warnings in `Vagrant` logs about Guest Extensions version is not match VirtualBox version try to install `vagrant-vbguest` plugin that automatically installs Guest Extensions of version which corresponds to your version of VirtualBox: `vagrant plugin install vagrant-vbguest`
* Windows users may fall into trouble with `VirtualBox` and `Hyper-V`, the latter is used by "native" Docker for Windows. Try to disable Hyper-V and use [Docker Toolbox](https://www.docker.com/products/docker-toolbox) instead in such case
