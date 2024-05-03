for i in seattle newyork london
do
    for j in 1 2 3
    do
        docker stop roach-$i-$j
        docker rm roach-$i-$j
        docker volume rm roach-$i-$j-data
	docker stop haproxy-$i
	docker rm haproxy-$i
    done
done
docker network rm us-east-1-net us-west-2-net eu-west-1-net uswest-useast-net useast-euwest-net uswest-euwest-net

