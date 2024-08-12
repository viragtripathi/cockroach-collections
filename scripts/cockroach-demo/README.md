# cockroach demo
https://www.cockroachlabs.com/docs/stable/cockroach-demo

## Using Docker

Docker compatible [*nix OS](https://en.wikipedia.org/wiki/Unix-like) and [Docker](https://docs.docker.com/get-docker) installed.

<br>Please have 4 vCPU*, 10GB RAM and 20GB storage for the single-region setup to function properly. Adjust the resources based on your requirements.</br>

***MacOS Users:*** If you don't have or can't get Docker Desktop then install docker and docker-compose using homebrew
I use docker with [colima](https://github.com/abiosoft/colima) for this example:

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
docker-compose up -d
````

### Start cockroach demo
| ℹ️                                                                 |
|:-------------------------------------------------------------------|
| cockroach demo doesn't support configuring the network interfaces. |

````cmd
docker exec -it cockroach-single-node ./cockroach demo --insecure --http-port=8081 --sql-port=26258
````
| ℹ️                                                                                                                                     |
|:---------------------------------------------------------------------------------------------------------------------------------------|
| CockroachDB Single-Node server is running on fixed sql port `26257` and http port `8080` so the demo one has to be on different ports. |

<details><summary>Expected output:</summary>
<p>

```bash
-------------------------------
docker exec -it cockroach-single-node ./cockroach demo --insecure --http-port=8081 --sql-port=26258
#
# Welcome to the CockroachDB demo database!
#
# You are connected to a temporary, in-memory CockroachDB cluster of 1 node.
#
# This demo session will send telemetry to Cockroach Labs in the background.
# To disable this behavior, set the environment variable
# COCKROACH_SKIP_ENABLING_DIAGNOSTIC_REPORTING=true.
#
# Beginning initialization of the movr dataset, please wait...
#
# The cluster has been preloaded with the "movr" dataset
# (MovR is a fictional vehicle sharing company).
#
# Reminder: your changes to data stored in the demo session will not be saved!
#
# If you wish to access this demo cluster using another tool, you will need
# the following details:
#
#   - Connection parameters:
#      (webui)    http://127.0.0.1:8081
#      (cli)      cockroach sql --insecure -p 26258 -d movr
#      (sql)      postgresql://root@127.0.0.1:26258/movr?sslmode=disable
#
# Server version: CockroachDB CCL v24.1.3 (aarch64-unknown-linux-gnu, built 2024/08/01 11:49:48, go1.22.5 X:nocoverageredesign) (same version as client)
# Cluster ID: 8473bdf7-11d9-45e2-ad5f-4fe309d6cf6f
# Organization: Cockroach Demo
#
# Enter \? for a brief introduction.
#
root@127.0.0.1:26258/movr>
-------------------------------
```

</p>
</details>

## Using macOS

### Download and install [CockroachDB](https://www.cockroachlabs.com/docs/releases?filters=mac) binary

### Start cockroach demo

* Start a cockroach demo instance in a terminal window by copying/pasting the line below:
````bash
script -c $(cockroach demo --insecure) /dev/null >/dev/null
````
* Now, access `cockroach demo` instance using built-in `sql` client or any other clients i.e. psql, isql, DBeaver, Java etc.
````bash
cockroach sql --url 'postgresql://root@0.0.0.0:26257/movr?sslmode=disable'
````

### Stop cockroach demo

````bash
kill $(ps aux | grep cockroach | grep -v grep | awk '{print $2}')
````

<br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br>
> **🦺**
> This is only for demo and testing purposes.