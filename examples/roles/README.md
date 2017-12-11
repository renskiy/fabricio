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

## Virtual Machine creation

Run `vagrant up` and wait until VM will be created.

## List of available commands

    fab --list

## Deploy

To deploy to a particular infrastructure you need to provide its name before any other command:

    fab vagrant nginx
    
This command will start deploy of `nginx` container to the `vagrant` infrastructure.

Also you can use `vagrant.confirm` command to skip confirmation dialog and start tasks execution immediately.

If no infrastructure selected then Fabricio will use Fabric's default roles definition (see `fabfile.py` for details). Also if there is no hosts found for a role then any task which needs to be executed on a remote host will be skipped.

## Deploy to localhost

Same configuration can be deployed to `localhost` infrastructure even without SSH daemon enabled locally:

    fab localhost nginx
    
This is possible due to Python "monkey patch" applied inside the `localhost` infrastructure definition (see [fabfile.py](fabfile.py#L28)).

## Parallel execution

Any Fabricio command can be executed in parallel mode. This mode provides advantages when you have more then one host to deploy to. Use `--parallel` option if you want to run command on all hosts simultaneously:

    fab --parallel vagrant.confirm nginx
    
*Choosing infrastructure using parallel mode only available with `.confirm` suffix due to limitations of Fabric*

## Customization

See "Hello World" [Customization](../hello_world/#customization) section.
