# Fabricio: Kubernetes configuration

This example shows how to deploy Kubernetes configuration consisting of two [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) with different number of containers: deployment1 (2 containers) and deployment2 (1 container).

## Requirements
* Fabricio 0.5 or greater
* [Vagrant](https://www.vagrantup.com)
* One from the [list of Vagrant supported providers](https://www.vagrantup.com/docs/providers/) (this example was tested with [VirtualBox](https://www.virtualbox.org/))

## Files
* __fabfile.py__, Fabricio configuration
* __k8s.yml__, Kubernetes configuration file
* __kube-canal.yml__, networking configuration for Kubernetes
* __kube-rbac.yml__, RBAC configuration for Kubernetes
* __README.md__, this file
* __Vagrantfile__, Vagrant config

## Virtual Machines creation

Run `vagrant up` and wait until VMs will be created.

## List of available commands

    fab --list

## Deploy

Before proceed you must initialize Kubernetes cluster first by running following command:

    fab kubernetes-init
    
After cluster has been successfully initialized everything is ready to work with Kubernetes configurations:

    fab k8s
    
## Deploy idempotency

Fabricio tries to deploy Kubernetes configuration either if content of provided configuration file was changed or any image of the configuration has newer version since last successful deploy attempt. However configuration deploy can be forced by using `force` flag:

    fab k8s:force=yes
    
## Parallel execution

Any Fabricio command can be executed in parallel mode. This mode provides advantages when you have more then one host to deploy to. Use `--parallel` option if you want to run command on all hosts simultaneously:

    fab --parallel k8s
    
## Rollback

Try to update configuration file (`k8s.yml`) and run deploy again:

    fab k8s
    
This will update Kubernetes configuration using new configuration file. After that you can return Kubernetes configuration to previous state by running 'rollback' command:

    fab k8s.rollback
    
## Customization

See also "Hello World" [Customization](../../hello_world/#customization) section.

### Custom configuration

Custom configuration can be provided using `filename` option:

```python
from fabricio import kubernetes

kubernetes.Configuration(
    name='k8s',
    options={
        'filename': 'my-k8s.yml',
    },
)
```

`filename` option (as well as any other option) can be a callable taking `kubernetes.Configuration` instance as parameter:

```python
from fabric import api as fab
from fabricio import kubernetes

def filename(
    configuration,  # type: kubernetes.Configuration
):
    # select configuration depending on infrastructure name
    # (see 'Infrastructures and roles' example)
    return '%s-k8s.yml' % (fab.env.infrastructure or 'default')

kubernetes.Configuration(
    name='my-k8s',
    options={
        'filename': filename,
    },
)
```
