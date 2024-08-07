# cockroach demo

# Prerequisites

Docker compatible [*nix OS](https://en.wikipedia.org/wiki/Unix-like) and [Docker](https://docs.docker.com/get-docker) installed.

<br>Please have 4 vCPU*, 10GB RAM and 20GB storage for the single-region setup to function properly. Adjust the resources based on your requirements.</br>

***MacOS Users:*** If you don't have or can't get Docker Desktop then install docker and docker-compose using homebrew
I use docker with [colima](https://github.com/abiosoft/colima):

`brew install docker`

`brew install docker-compose`

`brew install colima`

`colima start --cpu 4 --memory 10`

On my Apple M3 MacBook Pro, I have 8 CPUs and 20GB RAM allocated to docker.
````cmd
$ colima list
PROFILE    STATUS     ARCH       CPUS    MEMORY    DISK     RUNTIME    ADDRESS
default    Running    aarch64    8       20GiB     60GiB    docker
````

### Start Single-Node CockroachDB
````cmd
$ docker-compose up -d
````

### Start cockroach demo 
````cmd
$ docker exec -it cockroach-single-node ./cockroach demo --http-port=8040 --sql-port=26289
````
| ℹ️                                                                                                                        |
|:--------------------------------------------------------------------------------------------------------------------------|
| CockroachDB Single-Node server is running on fixed `26257` and `8080` ports so the demo one has to be on different ports. |

<br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br>
> **🦺**
> This is only for demo and testing purposes.