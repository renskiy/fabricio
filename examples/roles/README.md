# Fabricio: infrastructures

This example shows how to use roles within different infrastructures. There are one role and one infrastructure defined in [fabfile.py](fabfile.py). But you can define as many additional roles and infrastructures as you need.

## Requirements
* Fabricio 0.3.19 or greater
* [Vagrant](https://www.vagrantup.com)
* One from the [list of Vagrant supported providers](https://www.vagrantup.com/docs/providers/) (this example was tested with [VirtualBox](https://www.virtualbox.org/))

## Files
* __fabfile.py__, Fabricio configuration
* __README.md__, this file
* __Vagrantfile__, Vagrant config

## List of available commands

    fab --list

## Deploy

To deploy to a particular infrastructure you need to provide its name before any other command:

    fab vagrant nginx
    
This command will start deploy of `nginx` container to the `vagrant` infrastructure. Vagrant virtual machine creation will start automatically if needed.

Also you can use `vagrant.confirm` command to skip confirmation dialog and start tasks execution immediately.

If no infrastructure selected then Fabricio will use Fabric's default roles definition (see `fabfile.py` for details). Also if there is no hosts found for a role then any task which needs to be executed on a remote host will be skipped.

## Parallel execution

Any Fabricio command can be executed in parallel mode. This mode provides advantages when you have more then one host to deploy to. Use `--parallel` option if you want to run command on all hosts simultaneously:

    fab --parallel vagrant nginx

## Customization

See "Hello, World" [Customization](../hello_world/#customization) section.

## Issues

* If you see warnings in `Vagrant` logs about Guest Extensions version is not match VirtualBox version try to install `vagrant-vbguest` plugin that automatically installs Guest Extensions of version which corresponds to your version of VirtualBox: `vagrant plugin install vagrant-vbguest`
