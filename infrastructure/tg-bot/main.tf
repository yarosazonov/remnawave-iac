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

variable "panel_ip" {
  type = string
}

locals {
  bot_config = yamldecode(file("${path.module}/../../config/bot.yaml"))
}

data "cloudflare_zone" "main" {
  filter = {
    name = local.bot_config.domain.zone
  }
}

resource "cloudflare_dns_record" "bot" {
  zone_id = data.cloudflare_zone.main.id
  name    = local.bot_config.domain.bot_subdomain
  content = var.panel_ip
  type    = "A"
  proxied = false
  comment = "Managed by Terraform (Bot Stack)"
  ttl     = 300
}
