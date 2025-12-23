variable "nodes" {
  type = map(object({
    region = string
    plan   = optional(string, "vc2-1c-1gb") # Default to $5 plan
  }))
  description = "Map of nodes to deploy"
}

variable "cloudflare_zone" {
  type        = string
  description = "Panel domain name"
}

variable "PANEL_API_TOKEN" {
  type        = string
  description = "Remna panel API token"
}

variable "panel_api_base_url" {
  type        = string
  description = "Remna panel API base URL"
}

variable "panel_ip" {
  type        = string
  description = "Remna panel IP"
}

variable "node_port" {
  type        = number
  description = "Remna node port"
}

variable "config_profile_uuid" {
  type        = string
  description = "Remna config profile UUID"
}

variable "active_inbounds" {
  type        = list(string)
  description = "Remna active inbounds"
}


variable "admin_username" {
  description = "Username for the admin account that would be created durin provisioning"
  type        = string
}

variable "admin_pub_key_path" {
  description = "Path to the personal public ssh key. It will be injected alongside with automatically generated ansible_key"
  type        = string
}

variable "ansible_username" {
  description = "Username for the ansible account that would be created durin provisioning"
  type        = string
  default     = ""
}

variable "ansible_pub_key_path" {
  description = "Path to the ansible public ssh key."
  type        = string
  default     = ""
}

# This will be populated by TF_VAR_ansible_public_key from node-deploy.sh
variable "ansible_pub_key" {
  description = "Public key for the automated ansible user"
  type        = string
  default     = ""
}