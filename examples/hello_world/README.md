# Fabricio: Hello, World

This example shows how to deploy basic configuration consisting of a single container based on [official Nginx image](https://hub.docker.com/_/nginx/).

## Requirements
* Fabricio 0.3.17 or greater
* [Vagrant](https://www.vagrantup.com)
* One from the [list of Vagrant supported providers](https://www.vagrantup.com/docs/providers/) (this example was tested with [VirtualBox](https://www.virtualbox.org/))

## Files
* __fabfile.py__, Fabricio configuration
* __README.md__, this file
* __Vagrantfile__, Vagrant config

## Virtual Machine creation

Run `vagrant up` and wait until VM will be created.

## List of available commands

    fab --list

## Deploy

    fab nginx
    
## Parallel execution

Any Fabricio command can be executed in parallel mode. This mode provides advantages when you have more then one host to deploy to. Use `--parallel` option if you want to run command on all hosts simultaneously:

    fab --parallel nginx
    
## Deploy idempotency

Whenever you start deploy using serial or parallel mode Fabricio will always check if deploy is really necessary (usually by comparing new image id and image id of current container). Thus, deploy will be skipped if there is nothing to update. However, deploy may be forced using `force` parameter:

    fab nginx:force=yes

## Customization

`DockerTasks` takes a few additional optional arguments which can be used to customize your deploy process.

### Custom registry

This option usually used when target host has not direct access to image registry (e.g. hub.docker.com). If so, you can provide address and port of custom registry which will be used as an intermediate Docker image registry for you remote host:

    registry='custom-registry:5000'

Of course, your host must have access to this custom registry.

### Registry account

This option let you to provide Docker registry account to use with custom or default registry. For example:

    account='my_account'

### SSH tunneling

There is also ability to set up reverse SSH tunnel from remote host to your local network. This can be done by providing `ssh_tunnel_port` parameter:

    ssh_tunnel_port=5000
    
If `ssh_tunnel_port` value is set, then Fabricio will set up reverse SSH tunnel using custom (if provided) or image registry's host and port as tunnel's target every time when deploy process is taking place.
 
*Note, that official Docker registry (hub.docker.com) and most other registries behind load balancers (e.g. nginx) will not work over SSH tunnel (due to incorrect `Host` header sending by Docker daemon in such cases).*

## Issues

* If you see warnings in `Vagrant` logs about Guest Extensions version is not match VirtualBox version try to install `vagrant-vbguest` plugin that automatically installs Guest Extensions of version which corresponds to your version of VirtualBox: `vagrant plugin install vagrant-vbguest`
