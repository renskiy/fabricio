# Fabricio: Docker stacks

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

Before proceed you must initialize Docker swarm cluster first by running following command:

    fab swarm-init
    
After cluster has been successfully initialized everything is ready to work with stacks:

    fab stack
    
## Deploy idempotency

Fabricio will try to deploy stack either if content of provided Docker Compose configuration file was changed or any image of stack services has newer version since last successful deploy attempt. However stack deploy can be forced by using `force` flag:

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
from fabricio import docker

docker.Stack(
    name='my-stack', 
    options={
        'compose-file': 'my-compose.yml',
    },
)
```

`compose-file` option (as well as any other option) can be a callable taking `Stack` instance as parameter:

```python
from fabric import api as fab
from fabricio import docker

def compose_file(
    stack,  # type: docker.Stack
):
    # select compose file depending on infrastructure name
    # (see 'Infrastructures and roles' example)
    return '%s-compose.yml' % (fab.env.infrastructure or 'docker')

docker.Stack(
    name='my-stack', 
    options={
        'compose-file': compose_file,
    },
)
```
