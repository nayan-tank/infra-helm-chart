https://github.com/vmware-tanzu/velero-plugin-for-gcp
access setup guide

velero install \
    --provider gcp \
    --bucket upswing-global-backup \
    --plugins velero/velero-plugin-for-gcp:v1.11.1 \
    --secret-file ./velero/credentials-velero

kubectl apply -f ./velero/snapshot.yaml

velero backup create as1-dg-upswing-global \
    --include-namespaces store \
    --snapshot-volumes
