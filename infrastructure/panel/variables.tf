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


