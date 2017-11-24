# Fabricio: PostgreSQL master-slave deployment configuration

This configuration based on PostgreSQL [streaming replication](https://wiki.postgresql.org/wiki/Streaming_Replication).

## Requirements
* Fabricio 0.4.2 or greater
* [Vagrant](https://www.vagrantup.com)
* One from the [list of Vagrant supported providers](https://www.vagrantup.com/docs/providers/) (this example was tested with [VirtualBox](https://www.virtualbox.org/))

## Files
* __fabfile.py__, Fabricio configuration
* __pg_hba.conf__, PostgreSQL client authentication config
* __postgresql.conf__, PostgreSQL main config
* __README.md__, this file
* __recovery.conf__, PostgreSQL recovery config
* __Vagrantfile__, Vagrant config

## Virtual Machines creation

Run `vagrant up` and wait until VMs will be created.

## List of available commands

    fab --list

## Deploy

`--parallel` option must be specified in all cases or deploy will not start. This mode is used to automatically determine current master location.

### From scratch

    fab --parallel db
    
This case will be used at first time.
    
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
