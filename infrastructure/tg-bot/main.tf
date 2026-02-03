terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5"
    }
  }
}

provider "cloudflare" {
}

variable "cloudflare_zone" {
  type = string
}

variable "bot_subdomain" {
  type = string
}

variable "panel_ip" {
  type = string
}

data "cloudflare_zone" "main" {
  filter = {
    name = var.cloudflare_zone
  }
}

resource "cloudflare_dns_record" "bot" {
  zone_id = data.cloudflare_zone.main.id
  name    = var.bot_subdomain
  content = var.panel_ip
  type    = "A"
  proxied = false
  comment = "Managed by Terraform (Bot Stack)"
  ttl     = 300
}
