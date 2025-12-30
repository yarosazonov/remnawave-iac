# Remnawave nodes deploy automation

This repository contains the **Infrastructure as Code** setup for deploying and managing Remnawave nodes. It orchestrates **Terraform** and **Ansible** via a Python script, utilizing **Vultr** for compute and **Cloudflare** for DNS. 

## 📂 Directory Structure

- **`orchestration/`**: Contains the main `deploy.py` script that coordinates Terraform and Ansible.
- **`infrastructure/`**: Terraform configurations for provisioning Vultr instances, Cloudflare DNS and Remna panel nodes entries.
- **`configuration/`**: Ansible playbooks and roles for configuring the nodes.
- **`docs/`**: Architecture flowcharts.
- **`Makefile`**: Shortcuts for deployment commands.

## 🚀 Getting Started

### Prerequisites

- Python 3
- Terraform

### Setup

1. **Environment Variables**
   Copy the example environment file and fill in your secrets (Vultr API key, Cloudflare token, etc.):
   ```bash
   cp example.env .env
   nano .env
   ```

2. **Dependencies**
   Set up a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## 🛠️ Usage

Use the `make` commands to orchestrate the deployment:

| Command | Description |
|---------|-------------|
| `make deploy` | **Full Deployment**: Runs Terraform to provision infrastructure, then runs Ansible to configure it. |
| `make deploy-apply` | **Provision Only**: Runs Terraform Apply only. Useful for infrastructure updates without reconfiguration. |
| `make deploy-reboot` | **Reboot Nodes**: Same as deploy but forces a reboot of all the nodes. |
| `make deploy-destroy` | **Destroy**: Tears down the infrastructure.|

## 🧩 Orchestration Logic

The `orchestration/deploy.py` script handles the orchestration:
1. Load environment variables from `.env`.
2. Ensure SSH keys exist.
3. Generate `deployment.auto.tfvars.json` from non sensitive   environment variables.
4. Run Terraform to apply infrastructure changes.
5. Detect new nodes by comparing Terraform state.
6. Run Ansible playbooks (dynamically targeting new nodes or all nodes).

## 🔐 Security

- **SSH Keys**: The script generates a separate keypair for Ansible to access the nodes (stored in `~/.ssh/ansible_key`).
- **Firewall**: Access to the nodes is restricted to specific IP addresses (Node Exporter, Ansible, Node API)

