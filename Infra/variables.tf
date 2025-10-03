################ Provider Varibles ################

variable "gcp_project_id" {
  type = string
}

variable "gcp_region" {
  type = string
}

variable "gcp_zone" {
  type = string
}


################ Internal GKE ################

variable "enable_autopilot" {
  type = bool
}

variable "enable_l4_ilb_subsetting" {
  type = bool
}

variable "deletion_protection" {
  type = bool
}


# variable "services_secondary_range_name" {
#   type = string
# }
