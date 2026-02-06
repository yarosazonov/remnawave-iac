#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import json
import secrets
import string
import time
import logging
from pathlib import Path

from dotenv import load_dotenv, set_key
import yaml

# --- Configuration ---
SCRIPT_DIR = Path(__file__).resolve().parent
OPS_DIR = SCRIPT_DIR.parent
INFRA_DIR = (OPS_DIR / "infrastructure").resolve()
ANSIBLE_DIR = (OPS_DIR / "configuration").resolve()

PANEL_TF_DIR = INFRA_DIR / "panel"
NODES_TF_DIR = INFRA_DIR / "nodes"
BOT_DNS_TF_DIR = INFRA_DIR / "tg-bot"

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
    logger.info("🔑 Checking Credentials...")
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

def ensure_secrets() -> None:
    """Check for missing secrets in .env and generate them if empty."""
    env_path = OPS_DIR / ".env"
    
    # Secrets to check and their generation logic
    # (Key: (ByteLength/Length, Type))
    # Type: 'hex' (secrets.token_hex) or 'complex' (alphanumeric with restrictions)
    secrets_map = {
        "JWT_AUTH_SECRET": (32, 'hex'),
        "JWT_API_TOKENS_SECRET": (32, 'hex'),
        "POSTGRES_PASSWORD": (24, 'hex'),
        "WEBHOOK_SECRET_HEADER": (32, 'hex'),
        "METRICS_PASS": (16, 'hex'),
        "PANEL_ADMIN_PASSWORD": (24, 'complex'),
        "BACKUP_PASSWORD": (24, 'hex'),
        "KRISA_BOT_TG_WEBHOOK_SECRET": (32, 'hex')
    }
    
    updates_made = False
    
    for key, (length, s_type) in secrets_map.items():
        # strict check: missing OR empty string
        current_val = os.getenv(key)
        if current_val is None or current_val.strip() == "":
            logger.info(f"✨ Generating new secret for {key}...")
            
            if s_type == 'complex':
                # Generate a password that meets: ^(?=.*?[A-Z])(?=.*?[a-z])(?=.*?[0-9]).{24,}$
                alphabet = string.ascii_letters + string.digits
                while True:
                    new_secret = ''.join(secrets.choice(alphabet) for _ in range(length))
                    if (any(c.islower() for c in new_secret)
                            and any(c.isupper() for c in new_secret)
                            and any(c.isdigit() for c in new_secret)):
                        break
            else:
                new_secret = secrets.token_hex(length)
                
            set_key(env_path, key, new_secret)
            # Update current process env so subsequent steps see it
            os.environ[key] = new_secret
            updates_made = True
                  
    if updates_made:
        logger.info("💾 Secrets updated in .env")
        # Reload to be safe
        load_dotenv(env_path, override=True)

def run_terraform_cmd(args: list[str], cwd: Path, capture_output: bool = False, check: bool = True, log_error: bool = True) -> subprocess.CompletedProcess:
    """Run a terraform command in the specified directory."""
    cmd_str = f"terraform {' '.join(args)}"
    logger.debug(f"Running command: {cmd_str} in {cwd}")
    
    try:
        # Pass current env vars (including those loaded from .env)
        env = os.environ.copy()
        result = subprocess.run(
            ["terraform"] + args,
            cwd=cwd,
            check=check,
            env=env,
            text=True,
            capture_output=capture_output,
        )
        # If capturing json output - parse it
        if capture_output and "-json" in args:
            if result.returncode != 0:
                return None
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return None

        if capture_output and result.stdout:
            logger.debug(f"Command output: {result.stdout.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        if log_error:
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
        logger.info("🎯 Targeting defined hosts in playbook...")

    logger.debug(f"Running Ansible command: {' '.join(cmd)}")
    try:
        return subprocess.run(
            cmd, 
            cwd=ANSIBLE_DIR, 
            check=True,
        )
    except subprocess.CalledProcessError:
        logger.critical("❌ Ansible execution failed.")
        sys.exit(1)

def generate_tfvars(tf_module_name: str) -> None:
    """
    Generic function to generate tfvars.

    Creates a '{tf_module_name}.auto.tfvars.json' file in the respective module directory

    Args:
        tf_module_name (str):
            The name of the terraform module.
            Available options: 'panel', 'nodes'.
    """
    tf_dir = INFRA_DIR / tf_module_name
    inventory_file = f"{tf_module_name}.ini"
    
    try:
        tf_vars = {
            "ansible_username": ANSIBLE_USERNAME,
            "ansible_key_path": str(ANSIBLE_KEY_PATH),
            "ansible_inventory_path": str(ANSIBLE_DIR / f'inventory/{inventory_file}'),
        }

        # Specific logic for nodes
        if tf_module_name == "nodes":
             os.environ["TF_VAR_PANEL_API_TOKEN"] = os.environ["PANEL_API_TOKEN"]

        target = tf_dir / f"{tf_module_name}.auto.tfvars.json"
        with open(target, "w") as f:
            json.dump(tf_vars, f, indent=2)

        logger.debug(f"Generated {target}")

    except KeyError as e:
        logger.critical(f"❌ Missing required env var for {tf_module_name}: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"❌ Error generating {tf_module_name} tfvars: {e}")
        sys.exit(1)

def run_terraform_plan_and_apply(cwd: Path, destroy: bool = False) -> None:
    """Runs terraform plan, asks for confirmation, and applies if confirmed."""
    plan_type = "Destruction" if destroy else "Execution"
    logger.info(f"📋 Generating {plan_type} Plan...")
    
    cmd = ["plan", "-out=tfplan", "-detailed-exitcode"]
    if destroy:
        cmd.append("-destroy")

    process = run_terraform_cmd(
        cmd,
        cwd=cwd,
        check=False
    )
    
    plan_exit = process.returncode
    
    if plan_exit == 0:
        logger.info("✅ No infrastructure changes detected.")
        if (cwd / "tfplan").exists():
            (cwd / "tfplan").unlink()
    elif plan_exit == 2:
        logger.info("⚠️  CRITICAL: Review the plan above.")
        confirm = input("    Do you want to apply these changes? (y/n) ")
        if confirm.lower() not in ["y", "yes"]:
            logger.info("🚫 Execution is cancelled.")
            if (cwd / "tfplan").exists():
                (cwd / "tfplan").unlink()
            sys.exit(0) # Exit script if user cancels

        logger.info("🚀 Applying Plan...")
        run_terraform_cmd(["apply", "tfplan"], cwd=cwd)
        
        # Cleanup plan
        if (cwd / "tfplan").exists():
            (cwd / "tfplan").unlink()
    else:
        logger.critical("❌ Error generating Terraform plan.")
        sys.exit(1)

# === Workflow Handlers ===

def handle_panel(args):
    """Orchestrate Panel Deployment."""
    logger.info("🔹 Mode: PANEL")

    if args.action == "reboot":
        logger.info("🔄 Rebooting Panel...")
        run_ansible_playbook('reboot.yml', limit_arg="remnawave_panel", extra_vars=["target_hosts=remnawave_panel"])
        return

    if args.action == "restore":
        if not args.backup_file:
            logger.critical("❌ Backup file required for restore. Use: panel restore <backup_file>")
            sys.exit(1)
        backup_path = OPS_DIR / "backups" / args.backup_file
        if not backup_path.exists():
            logger.critical(f"❌ Backup file not found: {backup_path}")
            sys.exit(1)
        logger.info(f"🔄 Restoring Panel from: {args.backup_file}")
        if args.new_panel_secrets:
            logger.info("🔑 New secrets mode: will recreate admin and API tokens")

    ensure_secrets()
    generate_tfvars("panel")
    run_terraform_cmd(["init"], cwd=PANEL_TF_DIR)
    
    if args.action == "destroy":
        logger.warning("🔥 DESTROYING PANEL")
        run_terraform_plan_and_apply(PANEL_TF_DIR, destroy=True)
        logger.info("✅ Panel Destroyed.")
        return

    # Check if panel already exists
    existing_ip = run_terraform_cmd(["output", "-json", "panel_ip"], cwd=PANEL_TF_DIR, capture_output=True, check=False, log_error=False)
    
    # Plan & Apply
    run_terraform_plan_and_apply(PANEL_TF_DIR)
    # If we are here, it means either changes were applied or no changes detected via plan.
    
    # Retrieve Output
    panel_ip = run_terraform_cmd(["output", "-json", "panel_ip"], cwd=PANEL_TF_DIR, capture_output=True)
    panel_domain = run_terraform_cmd(["output", "-json", "panel_domain"], cwd=PANEL_TF_DIR, capture_output=True)
    
    # Determine if this was a fresh deploy or update
    # If we didn't have an IP before, or the IP changed = Reboot
    reboot_flag = "false"
    if not existing_ip or existing_ip != panel_ip:
        logger.info("🆕 Fresh Panel Deployment detected.")
        reboot_flag = "true"

    # Update panel.yaml with Panel IP 
    panel_file = OPS_DIR / "config" / "panel.yaml"
    if panel_file.exists():
        with open(panel_file, 'r') as f:
            content = f.read()
        
        import re
        # Replace the entire panel_ip line
        updated_content = re.sub(
            r'^\s*panel_ip:.*$',
            f'  panel_ip: {panel_ip}',
            content,
            flags=re.MULTILINE
        )
        
        with open(panel_file, 'w') as f:
            f.write(updated_content)
            
        logger.info(f"💾 Updated panel_ip in {panel_file}")


    logger.info(f"💾 Updated panel_ip in {panel_file}")
    logger.info(f"✅ Panel Server is Live: {panel_domain} ({panel_ip})")
    
    # Ansible
    if args.action == "restore":
        logger.info("🔧 Restoring Panel from Backup...")
        new_secrets = "true" if args.new_panel_secrets else "false"
        extra_vars = [f"reboot_infra={reboot_flag}", f"backup_file={backup_path}", f"new_panel_secrets={new_secrets}"]
        run_ansible_playbook('panel-restore.yml', extra_vars=extra_vars)
        logger.info("🎉 Panel Restore Complete!")
    else:
        logger.info("🔧 Configuring Panel Software...")
        extra_vars = [f"reboot_infra={reboot_flag}"]
        run_ansible_playbook('panel-fresh.yml', extra_vars=extra_vars)
        logger.info(f"🎉 Panel Deployment Complete!\n{panel_domain} ({panel_ip})")

def handle_node(args):
    """Orchestrate Node Deployment."""
    logger.info("🔹 Mode: NODE")

    if args.action == "reboot":
        logger.info("🔄 Rebooting Nodes...")
        run_ansible_playbook('reboot.yml', limit_arg="remna_nodes", extra_vars=["target_hosts=remna_nodes"])
        return

    # Create tfvars and init terraform for deploy/destroy
    generate_tfvars('nodes')
    run_terraform_cmd(["init"], cwd=NODES_TF_DIR)

    if args.action == "destroy":
        logger.warning("🔥 DESTROYING ALL NODES")
        run_terraform_plan_and_apply(NODES_TF_DIR, destroy=True)
        return

    if args.action == "deploy":
        reboot_flag = "false"
        logger.info("🔍 Checking existing nodes...")
        existing_nodes_map = run_terraform_cmd(["output", "-json", "node_data"], cwd=NODES_TF_DIR, capture_output=True, check=False, log_error=False) or {}
        existing_hostnames_set = set(existing_nodes_map.keys())

        if not existing_nodes_map:
            logger.info("ℹ️  No existing nodes found. Initializing fresh deployment...")

        run_terraform_plan_and_apply(NODES_TF_DIR)
        
        # Calculate new nodes
        # Calculate new nodes
        actual_nodes_map = run_terraform_cmd(["output", "-json", "node_data"], cwd=NODES_TF_DIR, capture_output=True, check=False, log_error=False) or {}
        actual_hostnames_set = set(actual_nodes_map.keys())
        new_hostnames = list(actual_hostnames_set - existing_hostnames_set)
        new_hostnames.sort()

        limit_arg = ""
        if new_hostnames:
            logger.info("🆕 New nodes detected:")
            # Reboot only new nodes by default 
            reboot_flag = "true"
            for h in new_hostnames:
                logger.info(f"   - {h}")
            limit_arg = ",".join(new_hostnames)

        logger.info("🔧 Configuring Nodes...")
        extra_vars = [f"reboot_infra={reboot_flag}"]
        run_ansible_playbook('node-configure.yml', limit_arg=limit_arg, extra_vars=extra_vars)

        logger.info("🎉 Node Deployment Complete!")
        if new_hostnames:
            logger.info("   New Nodes Deployed:")
            for h in new_hostnames:
               logger.info(f"   - {h}: {actual_nodes_map.get(h)}")

def handle_bot(args):
    """Orchestrate Bot Deployment."""
    logger.info("🔹 Mode: BOT")

    # Map friendly names to ansible roles
    bot_map = {
        "krisa": "krisa_bot"
    }

    bot_role = bot_map.get(args.bot_name)
    if not bot_role:
        logger.critical(f"❌ Unknown bot name: {args.bot_name}. Available: {list(bot_map.keys())}")
        sys.exit(1)
    
    # We need Panel IP.
    # Read from panel.yaml
    panel_file = OPS_DIR / "config" / "panel.yaml"
    panel_ip = None
    
    if panel_file.exists():
        with open(panel_file, 'r') as f:
            panel_config = yaml.safe_load(f) or {}
            panel_ip = panel_config.get('server', {}).get('panel_ip')

        
    # If missing during destroy, use dummy to satisfy Terraform
    if not panel_ip and args.action == "destroy":
         panel_ip = "0.0.0.0"

    if not panel_ip:
        logger.critical("❌ panel_ip not found in panel.yaml.")
        sys.exit(1)

    tf_vars = {
        "panel_ip": panel_ip,
    }
    
    target = BOT_DNS_TF_DIR / "tg-bot.auto.tfvars.json"
    with open(target, "w") as f:
        json.dump(tf_vars, f, indent=2)
    
    run_terraform_cmd(["init"], cwd=BOT_DNS_TF_DIR)

    if args.action == "destroy":
        logger.warning("🔥 DESTROYING BOT INFRA")
        run_terraform_plan_and_apply(BOT_DNS_TF_DIR, destroy=True)
        logger.info("✅ Bot Infra Destroyed.")

        logger.warning(f"🔥 REMOVING BOT SETUP ({args.bot_name})")
        run_ansible_playbook('bot-destroy.yml')
        logger.info(f"✅ BOT Setup Removed ({args.bot_name})")
        

    elif args.action == "deploy":
        # 1. Deploy Bot DNS
        logger.info("🌍 Managing Bot DNS Record...")
        run_terraform_plan_and_apply(BOT_DNS_TF_DIR)

        # 2. Deploy Bot Role
        logger.info(f"🤖 Deploying Bot: {args.bot_name}...")
        run_ansible_playbook('bot-deploy.yml', extra_vars=[f"bot_role={bot_role}"])
        logger.info(f"🎉 {args.bot_name} Bot Deployment Complete!")

def handle_backup(args):
    """Orchestrate Backup Setup."""
    logger.info("🔹 Mode: BACKUP")

    if args.action == "setup":
        logger.info("💾 Setting up Backups...")
        extra_vars = []
        if args.krisa:
            logger.info("   + Including Krisa Bot Backup")
            extra_vars.append("krisa_bot_backup=true")
        else:
            extra_vars.append("krisa_bot_backup=false")
            
        run_ansible_playbook('backup-setup.yml', extra_vars=extra_vars)
        logger.info("🎉 Backup Setup Complete!")

    elif args.action == "force":
        logger.info("⚡ Forcing Backups...")
        extra_vars = []
        if args.krisa:
            logger.info("   + Including Krisa Bot Backup")
            extra_vars.append("krisa_bot_backup=true")
        
        run_ansible_playbook('backup-force.yml', extra_vars=extra_vars)
        logger.info("🎉 Backup Execution Complete!")


def main():
    parser = argparse.ArgumentParser(description="KrisaVPN Deployment Orchestrator")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    
    subparsers = parser.add_subparsers(required=True, help="Subcommand to run")

    # Panel Subcommand
    panel_parser = subparsers.add_parser("panel", help="Manage Panel")
    panel_parser.add_argument("action", choices=["deploy", "destroy", "reboot", "restore"], help="Action to perform")
    panel_parser.add_argument("backup_file", nargs="?", help="Backup file for restore (in ops/backups/)")
    panel_parser.add_argument("--new-panel-secrets", action="store_true", help="Recreate admin and API tokens (use when original secrets are lost)")
    panel_parser.set_defaults(func=handle_panel)

    # Node Subcommand
    node_parser = subparsers.add_parser("node", help="Manage Node Infrastructure")
    node_parser.add_argument("action", choices=["deploy", "destroy", "reboot"], help="Action to perform")
    node_parser.set_defaults(func=handle_node)

    # Bot Subcommand
    bot_parser = subparsers.add_parser("bot", help="Deploy Bots")
    bot_parser.add_argument("action", choices=["deploy", "destroy"], help="Action to perform")
    bot_parser.add_argument("bot_name", nargs="?", default="krisa", help="Name of the bot to deploy (default: krisa)")
    bot_parser.set_defaults(func=handle_bot)

    # Backup Subcommand
    backup_parser = subparsers.add_parser("backup", help="Manage Backups")
    backup_parser.add_argument("action", choices=["setup", "force"], help="Action to perform")
    backup_parser.add_argument("--krisa", action="store_true", help="Include Krisa Bot backups")
    backup_parser.set_defaults(func=handle_backup)

    args = parser.parse_args()

    # Logger setup
    if args.verbose:
        logger.handlers[0].setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")

    # Load Env
    env_path = OPS_DIR / ".env"
    logger.info(f"✅ Loading secrets from {env_path}")
    load_dotenv(env_path, override=True)
    
    ensure_ssh_key()
    
    # Execute mapped function
    args.func(args)

if __name__ == "__main__":
    main()