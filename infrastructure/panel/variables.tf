variable "ansible_username" {
  description = "Username for the ansible account"
  type        = string
  default     = "ansible_automaton"
}

variable "ansible_key_path" {
  description = "Path to the ansible ssh key"
  type        = string
}

variable "ansible_inventory_path" {
  description = "Path to write the Ansible inventory fragment"
  type        = string
}
