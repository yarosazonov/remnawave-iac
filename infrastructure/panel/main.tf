terraform {
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
    vultr = {
      source  = "vultr/vultr"
      version = "~> 2.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5"
    }
  }

  backend "local" {
    # Independent state file for panel
    path = "state/terraform.tfstate"
  }
}

provider "vultr" {
  rate_limit  = 100
  retry_limit = 3
}

provider "cloudflare" {
}

# Load panel configuration from YAML
locals {
  panel_config = yamldecode(file("${path.module}/../../config/panel.yaml"))
}

# Reuse bootstrap script
data "template_file" "user_data" {
  template = file("${path.module}/../scripts/bootstrap.sh") # infrastructure/panel -> infrastructure -> scripts
  vars = {
    admin_username     = local.panel_config.server.admin.username
    admin_pub_key      = file("${local.panel_config.server.admin.key_path}.pub")
    ansible_username   = var.ansible_username
    ansible_pub_key    = file("${var.ansible_key_path}.pub")
    ansible_allowed_ip = local.panel_config.server.ansible_allowed_ip != null ? local.panel_config.server.ansible_allowed_ip : ""
  }
}

data "cloudflare_zone" "main" {
  filter = {
    name = local.panel_config.domain.zone
  }
}

resource "vultr_instance" "panel" {
  plan   = local.panel_config.server.plan
  region = local.panel_config.server.region
  os_id  = 2136 # Debian 12

  label    = local.panel_config.server.hostname
  hostname = local.panel_config.server.hostname

  tags        = ["auto-deploy", "remnawave", "panel"]
  enable_ipv6 = true
  backups     = "disabled"

  user_data = data.template_file.user_data.rendered

  lifecycle {
    ignore_changes = [
      user_data
    ]
  }
}

# Panel DNS Record
resource "cloudflare_dns_record" "panel" {
  zone_id = data.cloudflare_zone.main.id
  name    = local.panel_config.domain.panel_subdomain
  content = vultr_instance.panel.main_ip
  type    = "A"
  proxied = false
  comment = "Managed by Terraform"
  ttl     = 300
}

# Subpage DNS Record
resource "cloudflare_dns_record" "subscription" {
  # Create only if sub_subdomain is not empty
  count   = local.panel_config.domain.sub_subdomain != "" ? 1 : 0
  zone_id = data.cloudflare_zone.main.id
  name    = local.panel_config.domain.sub_subdomain
  content = vultr_instance.panel.main_ip
  type    = "A"
  proxied = false
  comment = "Managed by Terraform"
  ttl     = 300
}

# Inventory Fragment
resource "local_file" "ansible_inventory" {
  filename        = var.ansible_inventory_path
  content         = <<EOT
[remna_panel]
remna-panel ansible_host=${vultr_instance.panel.main_ip}

[remna_panel:vars]
ansible_user=${var.ansible_username}
ansible_ssh_private_key_file=${var.ansible_key_path}
EOT
  file_permission = "0644"
}


output "panel_ip" {
  value       = vultr_instance.panel.main_ip
  description = "Public IP of the Panel Server"
}

output "panel_domain" {
  value       = "${local.panel_config.domain.panel_subdomain}.${local.panel_config.domain.zone}"
  description = "Full domain name of the Panel"
}
