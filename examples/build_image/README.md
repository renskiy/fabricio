# Fabricio: Building Docker images

This example shows how to deploy configuration consisting of a single container based on custom image which automatically built from provided [Dockerfile](Dockerfile).

## Requirements
* Fabricio 0.4.6 or greater
* [Vagrant](https://www.vagrantup.com)
* One from the [list of Vagrant supported providers](https://www.vagrantup.com/docs/providers/) (this example was tested with [VirtualBox](https://www.virtualbox.org/))
* [Docker](https://www.docker.com/products/overview) for Linux/Mac/Windows
* Docker registry which runs locally on 5000 port, this can be reached out by executing following docker command: `docker run --name registry --publish 5000:5000 --detach registry:2`

## Files
* __Dockerfile__, used for building image
* __fabfile.py__, Fabricio configuration
* __README.md__, this file
* __Vagrantfile__, Vagrant config

## Virtual Machine creation

Run `vagrant up` and wait until VM will be created.

## List of available commands

    fab --list

## Deploy

    fab my_nginx
    
## Parallel execution

Any Fabricio command can be executed in parallel mode. This mode provides advantages when you have more then one host to deploy to. Use `--parallel` option if you want to run command on all hosts simultaneously:

    fab --parallel my_nginx

## Customization

See also "Hello World" [Customization](../hello_world/#customization) section.

### Custom `Dockerfile`

You can provide custom folder with `Dockerfile` by passing `build_path` parameter to `ImageBuildDockerTasks`:

```python
from fabricio import tasks

my_nginx = tasks.ImageBuildDockerTasks(
    # ...
    build_path='path/to/folder/with/dockerfile',
)
```
    
### Custom build params

Any `docker build` option can be passed directly to `my_nginx.prepare`*:

    fab my_nginx.prepare:tag,file=my-Dockerfile,squash=yes
    
After that you should manually call `push` and `upgrade` commands to finish deploy:

    fab my_nginx.push:tag
    fab my_nginx.upgrade:tag
    
\* Fabricio uses `--pull` and `--force-rm` options by default when building images.

## Issues

* Windows users may fall into trouble with `VirtualBox` and `Hyper-V`, the latter is used by "native" Docker for Windows. Try to disable Hyper-V and use [Docker Toolbox](https://www.docker.com/products/docker-toolbox) instead in such case
