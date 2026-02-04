variable "PANEL_API_TOKEN" {
  type        = string
  description = "Remna panel API token"
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

variable "ansible_inventory_path" {
  description = "Absolute path to the ansible inventory file"
  type        = string
}
