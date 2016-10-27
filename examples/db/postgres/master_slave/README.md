# Fabricio: PostgreSQL master-slave deployment configuration

This configuration based on PostgreSQL [streaming replication](https://wiki.postgresql.org/wiki/Streaming_Replication).

## Requirements
* Fabricio 0.3.7 or greater
* [Vagrant](https://www.vagrantup.com)
* One from the [list of Vagrant supported providers](https://www.vagrantup.com/docs/providers/) (this example was tested with [VirtualBox](https://www.virtualbox.org/))

## Files
* __fabfile.py__, Fabricio configuration
* __pg_hba.conf__, PostgreSQL client authentication config
* __postgresql.conf__, PostgreSQL main config
* __README.md__, this file
* __recovery.conf__, PostgreSQL recovery config
* __Vagrantfile__, Vagrant config

## Deploy

### From scratch

    fab --parallel db
    
At first, this will initiate 3 VMs creation using `Vagrant`: `docker1`, `docker2` and `docker3`. After VMs will be created `Fabricio` will initiate master-slave configuration deployment 'from scratch' with automatic master selection.

### Master fail

To initiate new master promotion you have to remove VM with current master:

1. `vagrant destroy <name_of_the_VM_with_master>`
2. Remove appropriate VM description from `Vagrantfile`

After that start deploy again:

    fab --parallel db
    
This will lead to a new master promotion.

### Adding new slave

1. Add new VM description to `Vagrantfile`
2. `fab --parallel db`

*Be sure you do not use old VM (e.g. with old failed master). New slave's VM must not have existing DB.*

## Issues

* If your host machine has more then one network adapter `Vagrant` will [ask](https://www.vagrantup.com/docs/networking/public_network.html#default-network-interface) you which one will be used
* Sometimes `VirtualBox` can't assign proper IP address to VM's bridged network adapter. In such cases destroying VM and creation new one will help (`vagrant reload` usually does not help)
