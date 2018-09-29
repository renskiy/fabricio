# Fabricio: Docker stack

This example shows how to deploy Docker stack consisting of a single service based on [official Nginx image](https://hub.docker.com/_/nginx/).

## Requirements
* Fabricio 0.4.2 or greater
* [Vagrant](https://www.vagrantup.com)
* One from the [list of Vagrant supported providers](https://www.vagrantup.com/docs/providers/) (this example was tested with [VirtualBox](https://www.virtualbox.org/))

## Files
* __fabfile.py__, Fabricio configuration
* __docker-compose.yml__, Docker Compose configuration file
* __README.md__, this file
* __Vagrantfile__, Vagrant config

## Virtual Machines creation

Run `vagrant up` and wait until VMs will be created.

## List of available commands

    fab --list

## Deploy

Before proceed you have to initialize Docker swarm cluster by running following command:

    fab swarm-init
    
*Note: use `fab swarm-reset` to reset cluster*
    
After cluster has been successfully initialized everything is ready to work with stacks:

    fab stack
    
## Deploy idempotency

Fabricio tries to deploy stack either if content of provided Docker Compose configuration file was changed or any image of stack services has newer version since last successful deploy attempt. However stack deploy can be forced by using `force` flag:

    fab stack:force=yes
    
## Parallel execution

Any Fabricio command can be executed in parallel mode. This mode provides advantages when you have more then one host to deploy to. Use `--parallel` option if you want to run command on all hosts simultaneously:

    fab --parallel stack
    
## Rollback

Try to update your docker-compose.yml and run deploy again:

    fab stack
    
This will update stack using new compose configuration. After that you can return stack to previous state by running 'rollback' command:

    fab stack.rollback
    
## Customization

See also "Hello World" [Customization](../../hello_world/#customization) section.

### Custom docker-compose.yml

Custom `docker-compose.yml` can be provided using `compose-file` option:

```python
from fabricio import docker, tasks

stack = tasks.DockerTasks(
    service=docker.Stack(
        name='my-stack',
        options={
            'compose-file': 'custom-docker-compose.yml',
        },
    ),
)
```

`compose-file` option (as well as any other option) can be a callable taking `docker.Stack` instance as parameter:

```python
from fabric import api as fab
from fabricio import docker, tasks

def compose_file(
    stack,  # type: docker.Stack
):
    # select compose file depending on infrastructure name
    # (see 'Infrastructures and roles' example)
    return '%s-compose.yml' % (fab.env.infrastructure or 'default')

stack = tasks.DockerTasks(
    service=docker.Stack(
        name='my-stack',
        options={
            'compose-file': compose_file,
        },
    ),
)
```

### Orchestrator select

Since Docker 17.12.0-CE (for Mac/Windows) it is possible to choose orchestrator for cluster by setting `DOCKER_ORCHESTRATOR` environment variable. In the example below Docker forced to use `kubernetes` orchestrator instead of default one:

```python
from fabricio import docker, tasks

stack = tasks.DockerTasks(
    service=docker.Stack(
        name='k8s-stack',
        options={
            'compose-file': 'docker-compose.yml',
        },
    ),
    env={
        'DOCKER_ORCHESTRATOR': 'kubernetes',
    },
)
```

*Note: `env` parameter became available from Fabricio 0.5.5*
