variable "nodes_vultr" {
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

variable "panel_url" {
  type        = string
  description = "Remna panel URL (including protocol, e.g. https://panel.example.com)"
}


variable "node_api_port" {
  type        = number
  description = "Remna node API port"
  default     = 2233
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
  default     = "admin"
}

variable "admin_key_path" {
  description = "Path to the personal ssh key. Public key will be injected alongside with automatically generated ansible_key"
  type        = string
}

variable "ansible_username" {
  description = "Username for the ansible account that would be created durin provisioning"
  type        = string
  default     = "ansible_automaton"
}

variable "ansible_key_path" {
  description = "Path to the ansible ssh key. Public key will be injected alongside with automatically generated ansible_key"
  type        = string
}

variable "ansible_allowed_ip" {
  description = "IP from which the Ansible user is allowed SSH access on port 22 (configured during bootstrap). Leave empty to allow from Any."
  type        = string
  default     = ""
}

variable "ansible_inventory_path" {
  description = "Absolute path to the ansible inventory file"
  type        = string
}
