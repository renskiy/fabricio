# Fabricio: PostgreSQL master-slave deployment configuration

This configuration based on PostgreSQL [streaming replication](https://wiki.postgresql.org/wiki/Streaming_Replication).

## Requirements
* Fabricio 0.3.16 or greater
* [Vagrant](https://www.vagrantup.com)
* One from the [list of Vagrant supported providers](https://www.vagrantup.com/docs/providers/) (this example was tested with [VirtualBox](https://www.virtualbox.org/))

## Files
* __fabfile.py__, Fabricio configuration
* __pg_hba.conf__, PostgreSQL client authentication config
* __postgresql.conf__, PostgreSQL main config
* __README.md__, this file
* __recovery.conf__, PostgreSQL recovery config
* __Vagrantfile__, Vagrant config

## List of available commands

    fab --list

## Deploy

### From scratch

    fab --parallel db
    
At first, this will initiate process of creation of three Virtual Machines (if not created yet) using `Vagrant` configuration: `docker1`, `docker2` and `docker3`. After that 'from scratch' case will automatically start.

### Master fail

To initiate new master promotion you may destroy VM with current master and run deploy again:

1. `vagrant destroy <name_of_the_VM_with_current_master>`
2. `fab --parallel db`

This will lead to a new master promotion.

### Adding new slave

Add new VM definition to `Vagrantfile` and then run deploy again:

    fab --parallel db

## Issues

* If you see warnings in `Vagrant` logs about Guest Extensions version is not match VirtualBox version try to install `vagrant-vbguest` plugin that automatically installs Guest Extensions of version which corresponds to your version of VirtualBox: `vagrant plugin install vagrant-vbguest`
