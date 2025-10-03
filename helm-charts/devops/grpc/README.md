kubectl create secret generic backend-mongo-ssl --from-file=ca.pem=./mongodb/cert/ops/ca.pem --from-file=client.pem=./mongodb/cert/ops/client.pem -n core
kubectl create secret generic backend-mongo-ssl --from-file=ca.pem=./mongodb/cert/ops-dev/ca.pem
--from-file=client.pem=./mongodb/cert/ops-dev/client.pem -n core
