#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import json
import time
import logging
from pathlib import Path

from dotenv import load_dotenv

# --- Configuration ---
SCRIPT_DIR = Path(__file__).resolve().parent
TF_DIR = (SCRIPT_DIR / "../infrastructure").resolve()
ANSIBLE_DIR = (SCRIPT_DIR / "../configuration").resolve()
ANSIBLE_KEY_PATH = Path("~/.ssh/ansible_key").expanduser()
ANSIBLE_USERNAME = "ansible_automaton"
LOG_FILE = SCRIPT_DIR / "deploy.log"


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for console and file."""
    # Create a custom logger
    # entry point __name__ = __main__
    logger = logging.getLogger("deploy") 
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers if re-running
    if logger.hasHandlers():
        logger.handlers.clear()

    # 1. Console Handler 
    c_handler = logging.StreamHandler(sys.stdout)
    c_level = logging.DEBUG if verbose else logging.INFO
    c_handler.setLevel(c_level)
    
    # Formatter to strip logger specific info from console messages
    c_formatter = logging.Formatter('%(message)s') 
    c_handler.setFormatter(c_formatter)
    
    # 2. File Handler (Forensics) - Detailed output
    f_handler = logging.FileHandler(LOG_FILE, mode='w')
    f_handler.setLevel(logging.DEBUG)
    f_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(funcName)s: %(message)s')
    f_handler.setFormatter(f_formatter)
    
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)
    
    return logger

# Initialize logger globally
logger = setup_logging()

def ensure_ssh_key() -> None:
    """Ensure the Ansible SSH key exists."""
    logger.info("🔑 [0/3] Checking Credentials...")
    if ANSIBLE_KEY_PATH.exists():
        logger.info(f"✅ Found existing Ansible Key: {ANSIBLE_KEY_PATH}")
    else:
        logger.info("⚠️  Key not found. Generating new Ansible Key...")
        ANSIBLE_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [
                    "ssh-keygen",
                    "-t",
                    "ed25519",
                    "-f",
                    str(ANSIBLE_KEY_PATH),
                    "-N",
                    "",
                    "-q",
                    "-C",
                    "ansible-auto-generated",
                ],
                check=True,
            )
            logger.info("✅ Key generated successfully.")
        except subprocess.CalledProcessError as e:
            logger.critical(f"❌ Failed to generate SSH key: {e}")
            sys.exit(1)

def run_terraform_cmd(args: list[str], cwd: str = TF_DIR, capture_output: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    """Run a terraform command and return output if requested."""
    cmd_str = f"terraform {' '.join(args)}"
    logger.debug(f"Running command: {cmd_str} in {cwd}")
    
    try:
        # Pass current env vars (including those loaded from .env)
        result = subprocess.run(
            ["terraform"] + args,
            cwd=cwd,
            check=check,
            env=os.environ,
            text=True,
            capture_output=capture_output,
        )
        if capture_output and result.stdout:
            logger.debug(f"Command output: {result.stdout.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {cmd_str}")
        if e.stderr:
            logger.error(f"Error output: {e.stderr.strip()}")
        raise

def run_ansible_playbook(playbook_name: str, limit_arg: str = "", extra_vars: list[str] = None) -> subprocess.CompletedProcess:
    """Run a specified Ansible playbook"""
    cmd = ["ansible-playbook", f'./playbooks/{playbook_name}'] 
    
    if extra_vars:
        for v in extra_vars:
            cmd.extend(['-e', v])
        
    if limit_arg:
        cmd.extend(['--limit', limit_arg])  
    else:
        logger.info("🎯 Targeting ALL nodes for configurations.")

    logger.debug(f"Running Ansible command: {' '.join(cmd)}")
    return subprocess.run(
        cmd, 
        cwd=ANSIBLE_DIR, 
        check=True, # Catches the error and raises CalledProcessError 
    )
    
def get_node_data_from_terraform() -> dict[str, str]:
    """Returns a dict of {hostname: ip}."""
    try:
        result = run_terraform_cmd(
            ["output", "-json", "node_data"], 
            capture_output=True
        )
        if not result.stdout.strip():
            logger.debug("Terraform output is empty.")
            return {}
        data = json.loads(result.stdout)
        # terraform output -json returns a dict where keys are hostnames, values are IPs
        return data
    except subprocess.CalledProcessError:
        # Fails if output doesn't exist yet
        logger.debug("Failed to get node data.")
        return {}

def create_tfvars_json() -> None:
    """Generates the deployment.auto.tfvars.json file."""
    # Required vars from environment
    try:
        # Parse list from env if possible, otherwise treat as string/HCL-ready string
        try:
            active_inbounds = json.loads(os.environ['ACTIVE_INBOUNDS'])
        except json.JSONDecodeError:
            # Fallback for manual string formatting compatibility or if already HCL-ish
            logger.warning("⚠️  Warning: ACTIVE_INBOUNDS is not valid JSON. Treating as raw string.")
            active_inbounds = os.environ['ACTIVE_INBOUNDS']

        tf_vars = {
            "cloudflare_zone": os.environ['CLOUDFLARE_ZONE'],
            "panel_api_url": os.environ['PANEL_API_URL'],
            "panel_ip": os.environ['PANEL_IP'],
            "config_profile_uuid": os.environ['CONFIG_PROFILE_UUID'],
            "active_inbounds": active_inbounds,
            "node_api_port": os.environ['NODE_API_PORT'],
            "admin_username": os.environ['ADMIN_USERNAME'],
            "admin_key_path": os.environ['ADMIN_KEY_PATH'],
            "ansible_username": ANSIBLE_USERNAME,
            "ansible_key_path": str(ANSIBLE_KEY_PATH),
            "ansible_allowed_ip": os.environ['ANSIBLE_STATIC_SSH_IP'],
            "ansible_inventory_path": str(ANSIBLE_DIR / 'inventory/hosts.ini')
        }

        # Terraform automatically loads tfvars.json files 
        with open(TF_DIR / "deployment.auto.tfvars.json", "w") as f:
            json.dump(tf_vars, f, indent=2)

        # Export secrets to Terraform 
        # VULTR_API_KEY and CLOUDFLARE_API_TOKEN are hooked up automatically by terraform 
        os.environ["TF_VAR_PANEL_API_TOKEN"] = os.environ["PANEL_API_TOKEN"]
        logger.debug("Generated deployment.auto.tfvars.json")

    except KeyError as e:
        logger.critical(f"❌ Error: Missing required environment variable: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="KrisaVPN Deployment Orchestrator"
    )
    parser.add_argument(
        "mode",
        nargs="?", # makes the arg "mode" optional
        default="default",
        choices=["default", "apply", "reboot", "destroy"],
        help="Deployment mode",
    )
    # Logger arg 
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", # makes the arg essentially a bool
        help="Enable verbose logging"
    )
    args = parser.parse_args()
    # Set verbose
    if args.verbose:
        logger.handlers[0].setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")

    mode = args.mode
    skip_ansible = False
    reboot_flag = "false"

    if mode == "default":
        # Default behavior: Terraform apply + Ansible
        # If new nodes are present they will be rebooted
        pass
    elif mode == "apply":
        # Terraform apply only. Useful for node teardowns.
        skip_ansible = True
    elif mode == "reboot":
        # Force reboot all nodes
        reboot_flag = "true"
    elif mode == "destroy":
        pass


    # 1. Credentials & Env
    ensure_ssh_key()

    env_path = SCRIPT_DIR.parent / ".env"
    logger.info(f"✅ Loading secrets from {env_path}")
    load_dotenv(env_path, override=True)

    # 2. Terraform
    logger.info("🚀 Initializing Deployment Pipeline...")
    logger.info("🏗️  [1/2] Provisioning...")

    # Init
    create_tfvars_json()
    run_terraform_cmd(["init"])

    # Destroy Flow
    if mode == "destroy":
        logger.info("🔥 DESTROY MODE ACTIVATED")
        logger.warning("⚠️  WARNING: This will DESTROY all resources managed by Terraform.")
        confirm = input("    Are you sure? (y/n) ")
        if confirm.lower() not in ["y", "yes"]:
            logger.info("🚫 Cancelled.")
            sys.exit(1)
        run_terraform_cmd(["destroy", "-auto-approve"])
        logger.info("✅ Infrastructure destroyed.")
        sys.exit(0)

    # 2a. Capture Existing State (to detect new nodes)
    logger.info("🔍 Checking existing nodes...")
    existing_nodes_map = get_node_data_from_terraform()
    existing_hostnames_set = set(existing_nodes_map.keys())

    if not existing_nodes_map:
        logger.info("ℹ️  No existing nodes found. Initializing fresh deployment...")

    # 2b. Plan
    logger.info("📋 Generating Execution Plan...")
    process = run_terraform_cmd(
        ["plan", "-out=tfplan", "-detailed-exitcode"],
        check=False
    )

    plan_exit = process.returncode

    if plan_exit == 0:
        logger.info("✅ No infrastructure changes detected.")
    elif plan_exit == 2:
        # Changes present
        logger.info("⚠️  CRITICAL: Review the plan above.")
        confirm = input("    Do you want to apply these changes? (y/n) ")
        if confirm.lower() not in ["y", "yes"]:
            logger.info("🚫 Deployment cancelled by user.")
            if (TF_DIR / "tfplan").exists():
                (TF_DIR / "tfplan").unlink()
            sys.exit(1)

        logger.info("🚀 Applying Plan...")
        run_terraform_cmd(["apply", "tfplan"])
    else:
        logger.critical("❌ Error generating Terraform plan.")
        sys.exit(1)

    # Cleanup plan
    if (TF_DIR / "tfplan").exists():
        (TF_DIR / "tfplan").unlink()

    if plan_exit == 0:
        # Optimization: No changes, so actual state == existing state
        actual_nodes_map = existing_nodes_map
        new_hostnames = []
    else:
        # Changes were applied, fetch fresh state
        actual_nodes_map = get_node_data_from_terraform()
        actual_hostnames_set = set(actual_nodes_map.keys())
        new_hostnames = list(actual_hostnames_set - existing_hostnames_set)
        new_hostnames.sort()

    limit_arg = ""

    if new_hostnames:
        logger.info("🆕 New nodes detected:")
        # Force reboot on new nodes
        reboot_flag = 'true'
        for h in new_hostnames:
            logger.info(f"   - {h}")

        limit_arg = ",".join(new_hostnames)

    # 3. Ansible
    if not skip_ansible:
        logger.info("🔧 [2/2] Applying Configuration...")

        # Constructing a list with extra vars to pass to ansible-playbook
        extra_vars = [
            f"reboot_nodes={reboot_flag}"
        ]
        
        try:
            run_ansible_playbook('node-configure.yml', limit_arg, extra_vars)
        except subprocess.CalledProcessError:
            logger.critical("❌ Ansible configuration failed.")
            sys.exit(1)
            
        logger.info("")
        logger.info("🎉 DEPLOYMENT SUCCESSFUL!")
        logger.info("   Nodes Deployed:")
        for h in new_hostnames:
            logger.info(f"   - {h}: {actual_nodes_map.get(h)}")
    else:
        logger.info("✅ Infrastructure applied successfully (Ansible skipped).")


if __name__ == "__main__":
    main()