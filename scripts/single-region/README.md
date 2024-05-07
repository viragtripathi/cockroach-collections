# Single-Region CockroachDB

# Prerequisites

Docker compatible [*nix OS](https://en.wikipedia.org/wiki/Unix-like) and [Docker](https://docs.docker.com/get-docker) installed.

<br>Please have 4 vCPU*, 10GB RAM and 20GB storage for the single-region setup to function properly. Adjust the resources based on your requirements.</br>

***MacOS Users:*** If you don't have or can't get Docker Desktop then install docker and buildx using homebrew
I use docker with [colima](https://github.com/abiosoft/colima):

`brew install docker`

`brew install docker-buildx`

`brew install colima`

`colima start --cpu 4 --memory 10`

On my Apple M3 MacBook Pro, I have 8 CPUs and 20GB RAM allocated to docker.
````cmd
$ colima list
PROFILE    STATUS     ARCH       CPUS    MEMORY    DISK     RUNTIME    ADDRESS
default    Running    aarch64    8       20GiB     60GiB    docker
````

### Start Multi-Region CockroachDB
````cmd
$ ./start_crdb_single_region.sh
````

### Stop Multi-Region CockroachDB
````cmd
$ ./stop_crdb_single_region.sh
````


<br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br>
> **🦺**
> This is only for demo and testing purposes.