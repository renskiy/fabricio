# Fabricio: Docker services

This example shows how to deploy Docker swarm mode configuration consisting of a single service based on [official Nginx image](https://hub.docker.com/_/nginx/).

## Requirements
* Fabricio 0.3.17 or greater
* [Vagrant](https://www.vagrantup.com)
* One from the [list of Vagrant supported providers](https://www.vagrantup.com/docs/providers/) (this example was tested with [VirtualBox](https://www.virtualbox.org/))

## Files
* __fabfile.py__, Fabricio configuration
* __README.md__, this file
* __Vagrantfile__, Vagrant config

## Virtual Machines creation

Run `vagrant up` and wait until VMs will be created.

## List of available commands

    fab --list

## Deploy

Before proceed you must initialize Docker swarm cluster first by running following command:

    fab swarm-init
    
After cluster has been successfully initialized everything is ready to work with services:

    fab nginx
    
## Deploy idempotency

Fabricio will not try to update service if no service parameters were changed after the last successful deploy attempt. However service update can be forced by using `force` flag:

    fab nginx:force=yes
    
## Parallel execution

Any Fabricio command can be executed in parallel mode. This mode provides advantages when you have more then one host to deploy to. Use `--parallel` option if you want to run command on all hosts simultaneously:

    fab --parallel nginx
    
## Rollback

Try to change some service options (e.g. change environment variable `FOO=42` to `FOO=hello`) and run deploy again:

    fab nginx
    
This will update service with new options. After that you can return service to previous state by running 'rollback' command:

    fab nginx.rollback
    
## Customization

See "Hello World" [Customization](../../hello_world/#customization) section.
