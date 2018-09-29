# Fabricio: Kubernetes configuration

This example shows how to deploy Kubernetes configuration consisting of two [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) with different number of containers: deployment1 (2 containers) and deployment2 (1 container).

## Requirements
* Fabricio 0.5 or greater
* [Vagrant](https://www.vagrantup.com)
* One from the [list of Vagrant supported providers](https://www.vagrantup.com/docs/providers/) (this example was tested with [VirtualBox](https://www.virtualbox.org/))

## Files
* __fabfile.py__, Fabricio configuration
* __configuration.yml__, Kubernetes configuration file
* __kube-canal.yml__, networking configuration for Kubernetes
* __kube-rbac.yml__, RBAC configuration for Kubernetes
* __README.md__, this file
* __Vagrantfile__, Vagrant config

## Virtual Machines creation

Run `vagrant up` and wait until VMs will be created.

## List of available commands

    fab --list

## Deploy

Before proceed you have to initialize Kubernetes cluster first by running following command:

    fab k8s-init
    
*Note: use `fab k8s-reset` to reset cluster*
    
After cluster has been successfully initialized everything is ready to work with Kubernetes configurations:

    fab service
    
## Deploy idempotency

Fabricio tries to deploy Kubernetes configuration either if content of provided configuration file was changed or any image of the configuration has newer version since last successful deploy attempt. However configuration deploy can be forced by using `force` flag:

    fab service:force=yes
    
## Parallel execution

Any Fabricio command can be executed in parallel mode. This mode provides advantages when you have more then one host to deploy to. Use `--parallel` option if you want to run command on all hosts simultaneously:

    fab --parallel service
    
## Rollback

Try to update configuration file (`configuration.yml`) and run deploy again:

    fab service
    
This will update Kubernetes configuration using new configuration file. After that you can return Kubernetes configuration to previous state by running 'rollback' command:

    fab service.rollback
    
## Customization

See also "Hello World" [Customization](../../hello_world/#customization) section.

### Custom configuration

Custom configuration file can be provided using `filename` option:

```python
from fabricio import kubernetes, tasks

service = tasks.DockerTasks(
    service=kubernetes.Configuration(
        name='my-service',
        options={
            'filename': 'custom-configuration.yml',
        },
    ),
)
```

`filename` option (as well as any other option) can be a callable taking `kubernetes.Configuration` instance as parameter:

```python
from fabric import api as fab
from fabricio import kubernetes, tasks

def filename(
    configuration,  # type: kubernetes.Configuration
):
    # select configuration depending on infrastructure name
    # (see 'Infrastructures and roles' example)
    return '%s-configuration.yml' % (fab.env.infrastructure or 'default')

service = tasks.DockerTasks(
    service=kubernetes.Configuration(
        name='my-service',
        options={
            'filename': filename,
        },
    ),
)
```
