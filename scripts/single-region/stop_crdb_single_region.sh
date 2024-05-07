for j in 1 2 3
  do
      docker stop roach-newyork-$j
      docker rm roach-newyork-$j
      docker volume rm roach-newyork-$j-data
  done
docker stop haproxy-newyork
docker rm haproxy-newyork
docker network rm us-east-1-net

