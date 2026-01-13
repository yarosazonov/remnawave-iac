# Remnawave IaC

Infrastructure as Code setup for deploying and managing **Remnawave Panel and Nodes**. Orchestrates **Terraform** and **Ansible** via a Python script, using **Vultr** for compute and **Cloudflare** for DNS.

## 📂 Directory Structure

```
ops/
├── orchestration/      # deploy.py - main orchestration script
├── infrastructure/
│   ├── panel/          # Terraform for panel provisioning
│   └── nodes/          # Terraform for nodes provisioning
├── configuration/
│   ├── playbooks/      # Ansible playbooks
│   └── roles/
│       ├── remna_panel/setup,caddy,creds,subpage
│       ├── remna_node/setup,logrotate
│       ├── ufw, docker, node_exporter, reboot, ...
├── Makefile            # Shortcuts for deployment commands
└── example.env         # Environment template
```

## 🚀 Getting Started

### Prerequisites

- Python 3
- Terraform

### Setup

1. **Environment Variables**
   ```bash
   cp example.env .env
   nano .env  # Fill in Vultr API key, Cloudflare token, etc.
   ```

2. **Python Dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## 🛠️ Usage

### Panel Commands

| Command | Description |
|---------|-------------|
| `make panel-deploy` | Deploy panel |
| `make panel-reboot` | Reboot panel server |
| `make panel-destroy` | Destroy panel infrastructure |

### Nodes Commands

| Command | Description |
|---------|-------------|
| `make nodes-deploy` | Deploy nodes |
| `make nodes-reboot` | Reboot all nodes |
| `make nodes-destroy` | Destroy nodes infrastructure |

## 🧩 Orchestration Logic

The `orchestration/deploy.py` script handles:

1. Load environment variables from `.env`
2. Ensure SSH keys and secrets exist
3. Generate Terraform tfvars from environment
4. Run Terraform (plan → apply)
5. Detect new instances by comparing state
6. Run Ansible playbooks (targeting new or all hosts)
7. Auto-reboot on fresh deployments

## 🔐 Security

- **SSH Keys**: Separate keypair for Ansible (`~/.ssh/ansible_key`)
- **Firewall (UFW)**: Restricts access to specific ports and IPs
