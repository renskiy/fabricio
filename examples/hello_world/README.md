# Fabricio: Hello World

This example shows how to deploy basic configuration consisting of a single container based on [official Nginx image](https://hub.docker.com/_/nginx/).

## Requirements
* Fabricio 0.3.17 or greater
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

    fab nginx
    
## Parallel execution

Any Fabricio command can be executed in parallel mode. This mode provides advantages when you have more then one host to deploy to. Use `--parallel` option if you want to run command on all hosts simultaneously:

    fab --parallel nginx
    
## Deploy idempotency

Whenever you start deploy using serial or parallel mode Fabricio will always check if deploy is really necessary (usually by comparing new image id and image id of current container). Thus, deploy will be skipped if there is nothing to update. However, deploy may be forced using `force` parameter:

    fab nginx:force=yes

## Customization

`DockerTasks` takes a few additional optional arguments which can be used to customize your deploy process.

### Intermediate (proxy) registry

This option usually used when remote host has not direct access to the image registry (e.g. hub.docker.com). If so, you can provide address and port of custom registry which will be used as an intermediate (or proxy, in other words) Docker image registry for you remote host:

    registry='private-registry:5000'

If such parameter as above was provided then Fabricio will always try to pull image from original image's registry and push this image to `private-registry:5000` which will be used by remote hosts instead of original one.

### Registry account

This option let you to provide custom Docker registry account to use with custom or default registry:

    account='my-account'

### SSH tunneling

There is also ability to set up reverse SSH tunnel from remote host to your local network. This can be done by providing `ssh_tunnel` parameter:

    ssh_tunnel='7000:example.com:5000'  # value syntax is the same as 'ssh -R' does
    
Providing such parameter as above will open port 7000 on the remote host for period of deployment and all packets sent to this port will be forwarded to `example.com:5000`.

#### Using proxy

While [Docker can work with proxy](https://docs.docker.com/engine/admin/systemd/#httphttps-proxy) you can run HTTP/HTTPS/SOCKS5 proxy and provide remote hosts access to this proxy by setting up SSH tunnel:

    ssh_tunnel='33128:proxy-host:3128'
    
Where `3128` is port which used by proxy running on `proxy-host`, and `33128` is port used for proxy on the remote side. In this case you must specify `HTTP_PROXY=http://localhost:33128` or `HTTPS_PROXY=https://localhost:33128` or `ALL_PROXY=socks5://localhost:33128` environment variable (depending on type of your proxy) in Docker settings on all remote hosts.

*New in 0.4.6*
    
### Local registry access over SSH tunnel

Suppose you have your own [private registry](https://hub.docker.com/_/registry/) running on localhost and listening on 5000 port. Then you can provide access to this registry for remote hosts by filling out following parameters:

    registry='localhost:5000',
    ssh_tunnel='5000:5000',
    
To set another port (and host) on remote side you can use `host_registry` option:

    registry='localhost:5000',
    ssh_tunnel='7000:5000',
    host_registry='localhost:7000',

*New in 0.4.6*
    
*Note, that official Docker registry (hub.docker.com) and most other registries behind HTTP router or load balancer (e.g. nginx or apache) will not work over SSH tunnel due to incorrect `Host` header using by Docker daemon while pulling images over SSH tunnel. But this can be fixed by using [proxy](#using-proxy).*
