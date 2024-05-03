# Multi-Region CockroachDB

# Prerequisites

Docker compatible [*nix OS](https://en.wikipedia.org/wiki/Unix-like) and [Docker](https://docs.docker.com/get-docker) installed.

<br>Please have 8-12 vCPU*, 20GB RAM and 20GB storage for the multi-region setup to function properly. Adjust the resources based on your requirements.</br>

***MacOS Users:*** If you don't have or can't get Docker Desktop then install docker and buildx using homebrew
I use docker with [colima](https://github.com/abiosoft/colima):

`brew install docker`

`brew install docker-buildx`

`brew install colima`

`colima start --cpu 12 --memory 20`

On my Apple M3 MacBook Pro, I have 8 CPUs and 20GB RAM allocated to docker.
````cmd
$ colima list
PROFILE    STATUS     ARCH       CPUS    MEMORY    DISK     RUNTIME    ADDRESS
default    Running    aarch64    8       20GiB     60GiB    docker
````

### Start Multi-Region CockroachDB
````cmd
$ ./start_crdb_multi_region.sh
````

### Stop Multi-Region CockroachDB
````cmd
$ ./stop_crdb_multi_region.sh
````


### Acknowledgements

Thanks to [Fabio](https://dev.to/cockroachlabs/simulating-a-multi-region-cockroachdb-cluster-on-localhost-with-docker-59f6) for documenting this.

<br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br>
> **🦺**
> This is only for demo and testing purposes.