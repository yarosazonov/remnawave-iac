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
    path = "terraform.tfstate"
  }
}

provider "vultr" {
  rate_limit  = 100
  retry_limit = 3
}

provider "cloudflare" {
}

# Reuse bootstrap script
data "template_file" "user_data" {
  template = file("${path.module}/../scripts/bootstrap.sh") # infrastructure/panel -> infrastructure -> scripts
  vars = {
    admin_username     = var.admin_username
    admin_pub_key      = file("${var.admin_key_path}.pub")
    ansible_username   = var.ansible_username
    ansible_pub_key    = file("${var.ansible_key_path}.pub")
    ansible_allowed_ip = var.ansible_allowed_ip
  }
}

data "cloudflare_zone" "main" {
  filter = {
    name = var.cloudflare_zone
  }
}

resource "vultr_instance" "panel" {
  plan   = var.panel_server_plan
  region = var.panel_server_region
  os_id  = 2136 # Debian 12

  label    = "remna-panel"
  hostname = "remna-panel"

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

# DNS Record: panel.domain.com
resource "cloudflare_dns_record" "panel" {
  zone_id = data.cloudflare_zone.main.id
  name    = var.panel_subdomain
  content = vultr_instance.panel.main_ip
  type    = "A"
  proxied = false
  comment = "Managed by Terraform"
  ttl     = 300
}

# DNS Record: sub.domain.com
resource "cloudflare_dns_record" "subscription" {
  # CONDITION ? TRUE : FALSE
  count   = var.subscription_subdomain != "" ? 1 : 0
  zone_id = data.cloudflare_zone.main.id
  name    = var.subscription_subdomain
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
[remnawave_panel]
${vultr_instance.panel.hostname} ansible_host=${vultr_instance.panel.main_ip}

[remnawave_panel:vars]
ansible_user=${var.ansible_username}
ansible_ssh_private_key_file=${var.ansible_key_path}
panel_domain=${var.panel_subdomain}.${var.cloudflare_zone}
sub_domain=${var.subscription_subdomain != "" ? "${var.subscription_subdomain}.${var.cloudflare_zone}" : ""}
EOT
  file_permission = "0644"
}


output "panel_ip" {
  value       = vultr_instance.panel.main_ip
  description = "Public IP of the Panel Server"
}

output "panel_domain" {
  value       = "${var.panel_subdomain}.${var.cloudflare_zone}"
  description = "Full domain name of the Panel"
}
