# Fabricio: Hello, World

This example shows how to deploy configuration consisting of a single container based on custom image which automatically built from provided [Dockerfile](Dockerfile).

## Requirements
* Fabricio 0.3.12 or greater
* [Vagrant](https://www.vagrantup.com)
* One from the [list of Vagrant supported providers](https://www.vagrantup.com/docs/providers/) (this example was tested with [VirtualBox](https://www.virtualbox.org/))
* [Docker](https://www.docker.com/products/overview) for Linux/Mac/Windows
* Docker registry which runs locally on 5000 port, this can be reached out by executing following docker command: `docker run --name registry --publish 5000:5000 --detach registry:2`

## Files
* __fabfile.py__, Fabricio configuration
* __README.md__, this file
* __Vagrantfile__, Vagrant config

## List of available commands

    fab --list

## Deploy

    fab my_nginx
    
At first, this will initiate creation of a new Virtual Machine (VM) using `Vagrant` configuration. Then deploy itself will start.

## Customization

See also "Hello, World" [Customization](../hello_world/#customization) section.

### Custom `Dockerfile`

You can provide custom folder with `Dockerfile` by passing `build_path` parameter:

    build_path='path_to_folder_with_dockerfile'

## Issues

* If you see warnings in `Vagrant` logs about Guest Extensions version is not match VirtualBox version try to install `vagrant-vbguest` plugin that automatically installs Guest Extensions of version which corresponds to your version of VirtualBox: `vagrant plugin install vagrant-vbguest`
