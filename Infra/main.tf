module "internal_gke" {
    source = "../modules/gke"
    gcp_region = var.gcp_region
    enable_autopilot = var.enable_autopilot
    enable_l4_ilb_subsetting = var.enable_l4_ilb_subsetting
    deletion_protection = var.deletion_protection
    # services_secondary_range_name = var.services_secondary_range_name 
}




