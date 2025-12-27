#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import json
import time

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TF_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../infrastructure"))
ANSIBLE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../configuration"))
ANSIBLE_KEY_PATH = os.path.expanduser("~/.ssh/ansible_key")
ANSIBLE_USERNAME = "ansible_automaton"


def load_env_file(filepath):
    """Simple parser for .env files to avoid external dependencies (python-dotenv)."""
    if not os.path.exists(filepath):
        print(f"❌ Error: .env file not found at {filepath}")
        sys.exit(1)

    print("✅ Secrets loaded from .env")
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                # Remove surrounding quotes if present
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                # Expand ~ to user home
                value = os.path.expanduser(value)
                # Expand $HOME and other env vars
                value = os.path.expandvars(value)
                os.environ[key] = value


def ensure_ssh_key():
    print("🔑 [0/3] Checking Credentials...")
    if os.path.exists(ANSIBLE_KEY_PATH):
        print(f"✅ Found existing Ansible Key: {ANSIBLE_KEY_PATH}")
    else:
        print("⚠️  Key not found. Generating new Ansible Key...")
        os.makedirs(os.path.dirname(ANSIBLE_KEY_PATH), exist_ok=True)
        subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-f",
                ANSIBLE_KEY_PATH,
                "-N",
                "",
                "-q",
                "-C",
                "ansible-auto-generated",
            ],
            check=True,
        )
        print("✅ Key generated successfully.")


def run_terraform_cmd(cmd_list, cwd=TF_DIR, capture_output=False):
    """Run a terraform command and return output if requested."""
    # Pass current env vars (including those loaded from .env)
    return subprocess.run(
        cmd_list,
        cwd=cwd,
        check=True,
        env=os.environ,
        text=True,
        capture_output=capture_output,
    )


def get_node_ips_from_terraform():
    """Returns a dict of {hostname: ip} and list of [ips]."""
    try:
        result = run_terraform_cmd(
            ["terraform", "output", "-json", "node_ips"], capture_output=True
        )
        if not result.stdout.strip():
            return {}, []
        data = json.loads(result.stdout)
        # terraform output -json returns a dict where keys are hostnames, values are IPs
        return data, list(data.values())
    except subprocess.CalledProcessError:
        # Fails if output doesn't exist yet
        return {}, []


def create_tf_vars_file():
    """Generates the deployment.auto.tfvars file."""
    # Required vars from environment
    try:
        content = f"""
cloudflare_zone      = "{os.environ['CLOUDFLARE_ZONE']}"
panel_api_url        = "{os.environ['PANEL_API_URL']}"
panel_ip             = "{os.environ['PANEL_IP']}"
config_profile_uuid  = "{os.environ['CONFIG_PROFILE_UUID']}"
active_inbounds      = {os.environ['ACTIVE_INBOUNDS']}
node_api_port        = "{os.environ['NODE_API_PORT']}"
ansible_username     = "{ANSIBLE_USERNAME}"
ansible_key_path     = "{ANSIBLE_KEY_PATH}"
admin_username       = "{os.environ['ADMIN_USERNAME']}"
admin_key_path       = "{os.environ['ADMIN_KEY_PATH']}"
ansible_allowed_ip   = "{os.environ['ANSIBLE_STATIC_SSH_IP']}"
ansible_inventory_path = "{os.path.join(ANSIBLE_DIR, 'inventory/hosts.ini')}"
"""
        with open(os.path.join(TF_DIR, "deployment.auto.tfvars"), "w") as f:
            f.write(content)

        # Export for Terraform CLI usage
        os.environ["TF_VAR_PANEL_API_TOKEN"] = os.environ["PANEL_API_TOKEN"]

    except KeyError as e:
        print(f"❌ Error: Missing required environment variable: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="KrisaVPN Node Deployment Orchestrator"
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="default",
        choices=["apply", "destroy", "reboot", "default"],
        help="Operation mode",
    )
    args = parser.parse_args()

    mode = args.mode
    skip_ansible = False
    reboot_flag = "false"

    if mode == "destroy":
        skip_ansible = True
    elif mode == "apply":
        skip_ansible = True
    elif mode == "reboot":
        reboot_flag = "true"
        mode = "default"
    elif mode == "default":
        # Default behavior: Apply + Ansible
        pass

    # 1. Credentials & Env
    ensure_ssh_key()
    # .env is in the parent 'ops' directory, not inside 'orchestration'
    env_path = os.path.join(SCRIPT_DIR, "../.env")
    load_env_file(os.path.abspath(env_path))

    # 2. Terraform
    print("🚀 Initializing Deployment Pipeline...")
    print("🏗️  [1/2] Provisioning Node...")

    create_tf_vars_file()

    # Init
    run_terraform_cmd(["terraform", "init"])

    # 2a. Capture Existing State (to detect new nodes)
    print("🔍 Checking existing nodes...")
    old_hostnames_map, old_ips = get_node_ips_from_terraform()
    existing_hostnames_set = set(old_hostnames_map.keys())

    # Destroy Flow
    if mode == "destroy":
        print("🔥 DESTROY MODE ACTIVATED")
        print("⚠️  WARNING: This will DESTROY all resources managed by Terraform.")
        confirm = input("    Are you sure? (y/n) ")
        if confirm.lower() not in ["y", "yes"]:
            print("🚫 Cancelled.")
            sys.exit(1)
        run_terraform_cmd(["terraform", "destroy", "-auto-approve"])
        print("✅ Infrastructure destroyed.")
        sys.exit(0)

    # 2b. Plan
    print("📋 Generating Execution Plan...")
    process = subprocess.run(
        ["terraform", "plan", "-out=tfplan", "-detailed-exitcode"],
        cwd=TF_DIR,
        env=os.environ,
    )

    plan_exit = process.returncode

    if plan_exit == 0:
        print("✅ No infrastructure changes detected.")
    elif plan_exit == 2:
        # Changes present
        print("⚠️  CRITICAL: Review the plan above.")
        confirm = input("    Do you want to apply these changes? (y/n) ")
        if confirm.lower() not in ["y", "yes"]:
            print("🚫 Deployment cancelled by user.")
            if os.path.exists(os.path.join(TF_DIR, "tfplan")):
                os.remove(os.path.join(TF_DIR, "tfplan"))
            sys.exit(1)

        print("🚀 Applying Plan...")
        run_terraform_cmd(["terraform", "apply", "tfplan"])
    else:
        print("❌ Error generating Terraform plan.")
        sys.exit(1)

    # Cleanup plan
    if os.path.exists(os.path.join(TF_DIR, "tfplan")):
        os.remove(os.path.join(TF_DIR, "tfplan"))

    # 2c. Calculate New Nodes
    all_hostnames_map, all_ips = get_node_ips_from_terraform()
    all_hostnames_set = set(all_hostnames_map.keys())

    new_hostnames = list(all_hostnames_set - existing_hostnames_set)
    new_hostnames.sort()

    target_ips = []
    limit_arg = ""

    if new_hostnames:
        print("🆕 New nodes detected:")
        for h in new_hostnames:
            print(f"   - {h}")

        # In python we can just use the comma joined string
        limit_arg = ",".join(new_hostnames)

        # For reporting (and old connectivity check logic if we ever needed it back)
        for h in new_hostnames:
            target_ips.append(all_hostnames_map[h])
    else:
        print("No new nodes detected. Defaulting to ALL nodes for configurations.")
        target_ips = all_ips

    if not all_ips:
        print("❌ Error: Terraform did not return any IP addresses.")
        sys.exit(1)

    # 3. Ansible
    if not skip_ansible:
        print("🔧 [2/2] Applying Configuration...")

        cmd = ["ansible-playbook", "./playbooks/node-configure.yml"]
        if limit_arg:
            print(f"🎯 Targeting ONLY new nodes: {limit_arg}")
            cmd.extend(["--limit", limit_arg])

        # Extra vars
        extra_vars = [
            f"node_api_port={os.environ['NODE_API_PORT']}",
            f"panel_ip={os.environ['PANEL_IP']}",
            f"panel_cert={os.environ['PANEL_CERT']}",
            f"monitoring_ip={os.environ['MONITORING_IP']}",
            f"reboot_nodes={reboot_flag}",
        ]

        # Pass -e with all vars
        for var in extra_vars:
            cmd.extend(["-e", var])

        subprocess.run(cmd, cwd=ANSIBLE_DIR, check=True, env=os.environ)

        print("")
        print("🎉 DEPLOYMENT SUCCESSFUL!")
        print("   Nodes Deployed:")
        for ip in target_ips:
            print(f"   - {ip}")
    else:
        print("✅ Infrastructure applied successfully (Ansible skipped).")


if __name__ == "__main__":
    main()
