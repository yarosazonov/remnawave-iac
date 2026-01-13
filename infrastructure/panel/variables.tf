variable "cloudflare_zone" {
  type        = string
  description = "Domain name (Zone)"
}

variable "panel_subdomain" {
  type        = string
  description = "Subdomain for the panel (e.g. 'panel')"
}

variable "subscription_subdomain" {
  type        = string
  description = "Subdomain for the subscription page (e.g. 'sub')"
}

variable "panel_server_plan" {
  type        = string
  description = "Vultr plan for the panel server"
  default     = "vhf-1c-2gb"
}

variable "panel_server_region" {
  type        = string
  description = "Vultr region for the panel server"
  default     = "ams"
}

variable "admin_username" {
  description = "Username for the admin account"
  type        = string
  default     = "admin"
}

variable "admin_key_path" {
  description = "Path to the personal ssh key"
  type        = string
}

variable "ansible_username" {
  description = "Username for the ansible account"
  type        = string
  default     = "ansible_automaton"
}

variable "ansible_key_path" {
  description = "Path to the ansible ssh key"
  type        = string
}

variable "ansible_allowed_ip" {
  description = "IP allowed for Ansible SSH access"
  type        = string
  default     = ""
}

variable "ansible_inventory_path" {
  description = "Path to write the Ansible inventory fragment"
  type        = string
}
