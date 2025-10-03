################ GKE ################

data "google_compute_network" "default" {
  name = "default"
}

data "google_compute_subnetwork" "default" {
  name = "default"
}


resource "google_compute_subnetwork" "default" {
  name = "gke-internal"

  ip_cidr_range = "10.0.0.0/16"
  region        = "asia-south1"

  stack_type       = "IPV4_ONLY"
  # ipv6_access_type = "INTERNAL" # Change to "EXTERNAL" if creating an external loadbalancer

  network = data.google_compute_network.default.id

  secondary_ip_range {
    range_name    = "services-range"
    ip_cidr_range = "10.20.0.0/20"
  }

  secondary_ip_range {
    range_name    = "pod-ranges"
    ip_cidr_range = "10.30.0.0/16"
  }
}


resource "google_container_cluster" "internal_gke" {
  name = "upswing-internal"

  location                 = var.gcp_region
  enable_autopilot         = var.enable_autopilot
  enable_l4_ilb_subsetting = var.enable_l4_ilb_subsetting

  network    = data.google_compute_network.default.id
  # subnetwork = data.google_compute_subnetwork.default.id
  subnetwork = google_compute_subnetwork.default.id

  ip_allocation_policy {
    stack_type                    = "IPV4"
    # services_secondary_range_name = "10.160.10.0/24"
    # cluster_secondary_range_name  = "10.160.20.0/24"

    services_secondary_range_name = google_compute_subnetwork.default.secondary_ip_range[0].range_name
    cluster_secondary_range_name  = google_compute_subnetwork.default.secondary_ip_range[1].range_name
  } 

  # Set `deletion_protection` to `true` will ensure that one cannot
  # accidentally delete this instance by use of Terraform.
  deletion_protection = var.deletion_protection

  # depends_on = [ data.google_compute_subnetwork.default ]
  depends_on = [ google_compute_subnetwork.default ]

}


################ Helm Chart ################

resource "null_resource" "helmfile_apply" {
  provisioner "local-exec" {
    command = "cd ../helm-charts/devops && ./helmfile sync -e dev-gcp-as1-core -e dev-gcp-as1-service"
  }

  provisioner "local-exec" {
    command = <<EOT
      gcloud container clusters get-credentials internal --region asia-south1 --project default
      cd ../../internal-gke/helm-charts/devops/ 
      helmfile sync -e dev-gcp-as1-core
      sleep 120
      helmfile sync -e dev-gcp-as1-service
    EOT
  }

  depends_on = [ google_container_cluster.internal_gke ]

  triggers = {
    always_run = timestamp()
  }

}