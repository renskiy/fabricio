# Fabricio: Docker Swarm

This example shows how to deploy Docker swarm mode configuration consisting of a single service based on [official Nginx image](https://hub.docker.com/_/nginx/).

## Requirements
* Fabricio 0.3.17 or greater
* [Vagrant](https://www.vagrantup.com)
* One from the [list of Vagrant supported providers](https://www.vagrantup.com/docs/providers/) (this example was tested with [VirtualBox](https://www.virtualbox.org/))

### Virtual Machines creation

Run `vagrant up` and wait until VMs will be created.

## Files
* __fabfile.py__, Fabricio configuration
* __README.md__, this file
* __Vagrantfile__, Vagrant config

## List of available commands

    fab --list

## Deploy

Before proceed you must initialize Docker swarm cluster first by running following command:

    fab swarm-init
    
At first, this command will start creation of three Virtual Machines (if not created yet) using `Vagrant` configuration. Then single Swarm manager and two Swarm workers will be set up.
 
After cluster has been successfully initialized Docker is ready to work with services:

    fab nginx
    
## Parallel execution

Any Fabricio command can be executed in parallel mode. This mode provides advantages when you have more then one host to deploy to. Use `--parallel` option if you want to run command on all hosts simultaneously:

    fab --parallel nginx
    
## Customization

See "Hello, World" [Customization](../../hello_world/#customization) section.

## Issues

* If you see warnings in `Vagrant` logs about Guest Extensions version is not match VirtualBox version try to install `vagrant-vbguest` plugin that automatically installs Guest Extensions of version which corresponds to your version of VirtualBox: `vagrant plugin install vagrant-vbguest`
