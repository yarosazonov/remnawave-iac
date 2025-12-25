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
    restapi = {
      source  = "Mastercard/restapi"
      version = "~> 2.0"
    }
  }

  backend "local" {
    # Store state in a subdirectory named "state"
    path = "state/terraform.tfstate"
  }
}

# Bootstrap script
data "template_file" "user_data" {
  template = file("${path.module}/scripts/bootstrap.sh")
  vars = {
    admin_username = var.admin_username
    admin_pub_key  = file("${var.admin_key_path}.pub")

    # Injected by node-deploy.sh
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

# === PROVIDERS ===

provider "restapi" {
  uri                  = var.panel_api_url
  write_returns_object = true
  debug                = true

  headers = {
    "Authorization" = "Bearer ${var.PANEL_API_TOKEN}",
    "Content-Type"  = "application/json"
    "Accept"        = "application/json"
  }

  create_method  = "POST"
  update_method  = "PATCH"
  destroy_method = "DELETE"
}

provider "vultr" {
  rate_limit  = 100
  retry_limit = 3
}

provider "cloudflare" {
}

# === RESOURCES ===

# 1. Vultr Instances (Iterate over var.nodes)
resource "vultr_instance" "nodes" {
  for_each = var.nodes

  # Hardware
  plan   = each.value.plan
  region = each.value.region
  os_id  = 2136 # Debian 12

  # Meta-data (Use the Map Key as the Hostname)
  label    = each.key
  hostname = each.key

  tags        = ["remnawave", "auto-deploy"]
  enable_ipv6 = true
  backups     = "disabled"

  # Inject your script
  user_data = data.template_file.user_data.rendered
}

# 2. Cloudflare Records (Iterate over the CREATED INSTANCES)
# We loop over 'vultr_instance.nodes' to ensure we have the IPs ready
resource "cloudflare_dns_record" "dns" {
  for_each = vultr_instance.nodes

  zone_id = data.cloudflare_zone.main.id

  # LOGIC: remna-node-jp-0 -> ["remna", "node", "jp", "0"] -> index 2 = "jp"
  name    = split("-", each.value.hostname)[2]
  content = each.value.main_ip
  type    = "A"
  comment = "Managed by terraform"
  ttl     = 300
  proxied = false
}

resource "restapi_object" "panel_nodes" {
  # Create a panel entry for every Vultr server
  for_each = vultr_instance.nodes

  path = "/nodes"

  # The Payload
  data = jsonencode({
    # "remna-node-jp-0" -> "jp-0"
    name    = format("%s-%s", split("-", each.key)[2], split("-", each.key)[3])
    address = each.value.main_ip
    port    = var.node_api_port

    # "remna-node-jp-0" -> "JP"
    countryCode = upper(split("-", each.key)[2])

    isTrafficTrackingActive = true
    trafficLimitBytes       = 3221225472000 # 3 TiB
    notifyPercent           = 90
    trafficResetDay         = 1

    configProfile = {
      activeConfigProfileUuid = var.config_profile_uuid
      activeInbounds          = var.active_inbounds
    }
  })

  # This tells Terraform: "The unique ID is in the 'uuid' field of the 'response' object"
  id_attribute = "response/uuid"

  # FORCE REPLACEMENT ON CHANGE
  # The API endpoint /api/nodes does not support standard REST PATCH /api/nodes/{id}
  # It expects PATCH /api/nodes with ID in body. The provider does not support this.
  lifecycle {
    replace_triggered_by = [
      terraform_data.node_config_hash[each.key]
    ]
    ignore_changes = [
      data
    ]
  }
}

# Helper resource to track configuration changes and force replacement
resource "terraform_data" "node_config_hash" {
  for_each = var.nodes

  input = jsonencode({
    port            = var.node_api_port
    config_profile  = var.config_profile_uuid
    active_inbounds = var.active_inbounds
    # Add other fields that might change and require replacement
    vultr_id = vultr_instance.nodes[each.key].id
  })
}

# Ansible inventory file generation
resource "local_file" "ansible_inventory" {
  filename = "${path.module}/../ansible/inventory/hosts.ini"

  # Contents of the inventory file
  content = <<EOT
[remna_nodes]
%{for hostname, node in vultr_instance.nodes~}
${hostname} ansible_host=${node.main_ip}
%{endfor~}

[remna_nodes:vars]
ansible_user=${var.ansible_username} 
ansible_ssh_private_key_file=${var.ansible_key_path}
panel_ip=${var.panel_ip}
EOT

  file_permission = "0644"
}

output "node_ips" {
  description = "Map of Hostnames to Public IPs"
  value = {
    for key, instance in vultr_instance.nodes :
    key => instance.main_ip
  }
}
