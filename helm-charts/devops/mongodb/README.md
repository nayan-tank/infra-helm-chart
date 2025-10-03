```
rs.initiate({_id: "rs0", version: 1,
   members: [
     { _id: 0, host: "mongo-db-0.mongo.upswing-operation.svc.cluster.local:27017" },
     { _id: 1, host: "mongo-db-1.mongo.upswing-operation.svc.cluster.local:27017" },
     { _id: 2, host: "mongo-db-2.mongo.upswing-operation.svc.cluster.local:27017" }
   ]
})


rs.initiate({_id: "rs0", version: 1, members: [{ _id: 1, host: "35.244.54.34:27017" }, { _id: 0, host: "34.93.195.216:27017" }, { _id: 2, host: "34.100.146.185:27017" }]})
var cfg = {
  _id: "rs0",
  members: [
    { _id: 0, host: "35.244.54.34:27017" },
    { _id: 1, host: "34.93.195.216:27017" },
    { _id: 2, host: "34.100.146.185:27017" }
  ]
}
rs.reconfig(cfg, { force: true })


kubectl exec -it mongo-db-1 -n upswing-operation -- mongosh


 rs.initiate({
...   _id: "rs0",
...   version: 1,
...   members: [
...     { _id: 0, host: "10.42.129.197:27017" },
...     { _id: 1, host: "10.42.129.92:27018" },
...     { _id: 2, host: "10.42.129.199:27019" }
...   ]
... });

kubectl exec -it mongo-db-0 -n upswing-operation -- mongosh

kubectl get pods -n upswing-operation -o wide

 use student
switched to db student
rs0 [direct: primary] student> db.users.insertOne({ name: "John Doe", email: "john.doe@example.com" })

  acknowledged: true,
  insertedId: ObjectId('66756dbad8c4fb2cdca26a13')
rs0 [direct: primary] student>
```


openssl req -passout pass:password -new -x509 -days 3650 -extensions v3_ca -keyout ca_private.pem -out ca.pem -subj "/CN=server/OU=MONGO/O=UPSWING/L=PUNE/ST=MH/C=IN"

openssl req -newkey rsa:4096 -nodes -out node.csr -keyout node.key -subj '/CN=server/OU=MONGO/O=UPSWING/L=PUNE/ST=MH/C=IN'

openssl req -newkey rsa:4096 -nodes -out client.csr -keyout client.key -subj '/CN=DbUser/OU=MONGO_CLIENTS/O=UPSWING/L=MH/ST=PN/C=IN'


openssl x509 -passin pass:password -sha256 -req -days 3650 -in client.csr -CA ca.pem -CAkey ca_private.pem -CAcreateserial -out client-signed.crt


openssl x509 -passin pass:password -sha256 -req -days 3650 -in node.csr -CA ca.pem -CAkey ca_private.pem -CAcreateserial -out node-signed.crt -extensions v3_req -extfile <(
cat << EOF
[ v3_req ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = mongo-db-0.mongodb-svc.ops.svc.cluster.local
DNS.2 = mongo-db-1.mongodb-svc.ops.svc.cluster.local
DNS.3 = mongo-db-2.mongodb-svc.ops.svc.cluster.local
DNS.4 = mongodb-svc.ops.svc.cluster.local
DNS.5 = mongo-db-0
DNS.6 = mongo-db-1
DNS.7 = mongo-db-2
EOF
)

cat client-signed.crt client.key > client.pem
cat node-signed.crt node.key > node.pem


db.getSiblingDB("$external").runCommand({createUser:"C=IN,ST=MH,L=PUNE,O=UPSWING,OU=MONGO_CLIENTS,CN=Admin",roles:[{role:"root",db:"admin"}]})


mongosh --host localhost --port 27017 --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem

mongosh --host mongo-db-0.mongodb-svc.ops.svc.cluster.local --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile
/ssl/custom/client.pem --eval "db.adminCommand('ping')"
mongosh --host mongodb-svc.ops.svc.cluster.local --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile
/ssl/custom/client.pem --eval "db.adminCommand('ping')"
mongosh --host mongo-service.ops.svc.cluster.local --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile
/ssl/custom/client.pem --eval "db.adminCommand('ping')"
mongosh --host db.service.upswing.global --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile
/ssl/custom/client.pem --eval "db.adminCommand('ping')"

```
mongosh --host 34.100.146.185 --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem --eval "db.adminCommand('ping')"
```
mongosh --username YWRtaW51c2Vy --password cGFzc3dvcmQxMjM= --host localhost --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem --eval 'rs.status().members'

```
kubectl exec mongo-db-0 -n ops -- mongosh --quiet localhost:27017/admin --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem --username adminuser --password password123 -eval 'printjson(JSON.stringify({members: rs.conf().members, version: rs.conf().version}, null, 2))'
```

USNAME=$(kubectl get secret mongo-creds -n ops -o jsonpath='{.data.username}' | base64 --decode)
PASSWORD=$(kubectl get secret mongo-creds -n ops -o jsonpath='{.data.password}' | base64 --decode)

kubectl exec mongo-db-0 -n ops -- mongosh --host mongo-db-1.mongodb-svc.ops.svc.cluster.local --tls --tlsCAFile
/ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem

admin = db.getSiblingDB("admin")
admin.createUser(
  {
    user: "admin",
    pwd: "x24n3hjJDk3DDl2S",
    roles: [ { role: "userAdminAnyDatabase", db: "admin" } ]
  }
)
db.getSiblingDB("admin").auth("admin", "x24n3hjJDk3DDl2S")


db.getSiblingDB("admin").createUser(
  {
    "user" : "clusterAdmin",
    "pwd" : "js23NHS93njds3DS#skd",
    roles: [ { "role" : "clusterAdmin", "db" : "admin" } ]
  }
)

```
kubectl exec mongo-db-0 -n ops -- mongosh --quiet localhost:27017/admin --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem --username clusterAdmin --password js23NHS93njds3DS#skd --eval "JSON.stringify({members: rs.conf().members, version: rs.conf().version}, null, 2)"
kubectl exec mongo-db-0 -n ops -- mongosh --quiet localhost:27017/admin --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem --username admin --password x24n3hjJDk3DDl2S --eval "JSON.stringify({members: rs.conf().members, version: rs.conf().version}, null, 2)"
```

```
kubectl exec mongo-db-0 -n ops -- mongosh --quiet localhost:27017/admin --username clusterAdmin --password js23NHS93njds3DS#skd --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem --eval "rs.status()"
kubectl exec mongo-db-0 -n ops -- mongosh --quiet localhost:27017/admin --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem --eval 'rs.initiate({"_id": "rs0", "version": 1, "members": [{"_id": 0, "host": "mongo-db-0.store.dev.upswing.global:27017"}, {"_id": 1, "host": "mongo-db-1.store.dev.upswing.global:27017"}, {"_id": 2, "host": "mongo-db-2.store.dev.upswing.global:27017"}]})'
```

```
kubectl exec mongo-db-0 -n ops -- mongosh --quiet db.service.upswing.global:27017/admin --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem --eval "JSON.stringify({members: rs.conf().members, version: rs.conf().version}, null, 2)"
```

kubectl exec mongo-db-0 -n ops -- mongosh --quiet mongo-db-0.mongodb-svc.ops.svc.cluster.local:27017/admin --tls
--tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem --username admin --password
x24n3hjJDk3DDl2S --eval "JSON.stringify({members: rs.conf().members, version: rs.conf().version}, null, 2)"

mongosh --host 35.200.137.164 --tls --tlsCAFile ./cert/ops/ca.pem --tlsCertificateKeyFile ./cert/ops/client.pem
--username admin --password x24n3hjJDk3DDl2S


use admin
db.getSiblingDB("$external").runCommand(
  {
    createUser: "C=IN,ST=MH,L=PUNE,O=UPSWING,OU=MONGO_CLIENTS,CN=Admin",
    roles: [
       { role: "root", db: "admin" }
    ]
  }
)

db.getSiblingDB("admin").createUser({"user": "admin", "pwd": "x24n3hjJDk3DDl2S", "roles": [{ "role": "userAdminAnyDatabase", "db": "admin" }]})

db.grantRolesToUser("clusterAdmin", [{ role: "readWriteAnyDatabase", db: "admin" }])

```
kubectl exec mongo-db-0 -n ops-dev -- mongosh --quiet localhost:27017/admin --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem --eval 'rs.initiate({_id: "rs0", version: 1, members: [{ _id: 1, host: "35.244.54.34:27017" }, { _id: 0, host: "34.93.195.216:27017" }, { _id: 2, host: "34.100.146.185:27017" }]})'
```

# namespace: ops-mohg

kubectl exec mongo-db-0 -n ops -- mongosh --quiet localhost:27017/admin --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem --username clusterAdmin --password js23NHS93njds3DS#skd --eval "rs.status()"
kubectl exec mongo-db-0 -n ops-mohg -- mongosh --quiet localhost:27017/admin --tls --tlsCAFile /ssl/custom/ca.pem --tlsCertificateKeyFile /ssl/custom/client.pem --username admin --password x24n3hjJDk3DDl2S --eval "rs.status()"

kubectl exec mongo-db-0 -n ops-mohg -- mongosh --quiet localhost:27017/admin --tls --tlsCAFile /ssl/custom/ca.pem
--tlsCertificateKeyFile /ssl/custom/client.pem --eval "rs.status()"
kubectl port-forward mongo-db-1 27030:27017 -n ops-mohg
