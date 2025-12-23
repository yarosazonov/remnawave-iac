#!/bin/bash
set -e # Exit immediately if any command fails

# Get the absolute path of the current folder 
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# --- CONFIGURATION ---
# Adjust these paths if your folder structure differs
TF_DIR="$SCRIPT_DIR/terraform"
ANSIBLE_DIR="$SCRIPT_DIR/ansible"
INVENTORY_FILE="$ANSIBLE_DIR/inventory/hosts.ini"
ANSIBLE_USERNAME="ansible_automaton"
ANSIBLE_KEY_PATH="$HOME/.ssh/ansible_key"
VAULT_PASS_FILE=".vault_pass"
# ---------------------



# --- 0. CREDENTIAL CHECK ---
echo "🔑 [0/3] Checking Credentials..."

if [ -f "$ANSIBLE_KEY_PATH" ]; then
    echo "✅ Found existing Ansible Key: $ANSIBLE_KEY_PATH"
else 
    echo "⚠️  Key not found. Generating new Ansible Key..."
    mkdir -p "$(dirname "$ANSIBLE_KEY_PATH")"
    # Generate ed25519 key, no passphrase (-N ""), quiet (-q)
    ssh-keygen -t ed25519 -f "$ANSIBLE_KEY_PATH" -N "" -C "ansible-auto-generated" -q
    echo "✅ Key generated successfully."
fi  

# Loading .env
if [ -f ".env" ]; then
    source .env
    echo "✅ Secrets loaded from .env"
else
    echo "❌ Error: .env file not found!"
    exit 1
fi


# --- 1. Terraform: Provision Infrastructure & Bootstrap User ---
echo "🚀 Initializing Deployment Pipeline..."
echo "🏗️  [1/3] Provisioning Node..."

# Inject variables into Terraform
export TF_VAR_ansible_username=$ANSIBLE_USERNAME
export TF_VAR_ansible_pub_key_path="${ANSIBLE_KEY_PATH/#$HOME/~}"
export TF_VAR_ansible_pub_key=$(cat "${ANSIBLE_KEY_PATH}.pub")
# Loaded with source .env
export TF_VAR_PANEL_API_TOKEN="$PANEL_API_TOKEN"

cd "$TF_DIR"

# Initializing
terraform init

# This calculates the state changes and saves them to 'tfplan'
echo "📋 Generating Execution Plan..."
terraform plan -out=tfplan

# pause  to validate 
echo "⚠️  CRITICAL: Review the plan above."
read -p "    Do you want to apply these changes? (y/n) " -r
echo "" 

if [[ ! $REPLY =~ ^[Yy](es)?$ ]]; then
    echo "🚫 Deployment cancelled by user. No changes made."
    rm -f tfplan # Cleanup
    exit 1
fi

# Apply 
echo "🚀 Applying Plan..."
terraform apply "tfplan"

# Cleanup
rm -f tfplan

# Extract IP using jq
raw_ips=$(terraform output -json node_ips | jq -r 'values[]')
# Convert to a bash array
ALL_IPS=($raw_ips)

if [ ${#ALL_IPS[@]} -eq 0 ]; then
    echo "❌ Error: Terraform did not return any IP addresses."
    exit 1
fi



# --- 2. Connectivity Check ---
echo "⏳ [2/3] Verifying connectivity for ${#ALL_IPS[@]} node(s)..."

# Loop through every IP in the array
for IP in "${ALL_IPS[@]}"; do
    echo "---------------------------------------------------"
    echo "🔍 Target: $IP"
    
    echo "🧹 Cleaning up old host keys..."
    ssh-keygen -R "$IP" 2>/dev/null

    echo "📡 Waiting for SSH to become available..."
    
    # Reset counter for this specific node
    count=0
    MAX_RETRIES=50 # 50 * (3s + ~2s) = ~ 4 minutes timeout

    while [ $count -lt $MAX_RETRIES ]; do
        # Try connection
        if ssh -o BatchMode=yes -o ConnectTimeout=2 -o StrictHostKeyChecking=no -i "$ANSIBLE_KEY_PATH" $ANSIBLE_USERNAME@$IP "echo 'ready'" &>/dev/null; then
            echo "✅ Connected to $IP!"
            break # Break the 'while', move to next IP in 'for' loop
        fi

        count=$((count + 1))
        
        # Timeout Logic
        if [ $count -eq $MAX_RETRIES ]; then
            echo "❌ Critical Error: Timed out waiting for node $IP."
            exit 1
        fi

        # Scientific notation for progress: Print a dot without newline
        echo -n "."
        sleep 3
    done
    echo "" # Newline for clean formatting
done

echo "✅ All nodes are online and reachable."


# --- 3. Ansible: Configuration & App Deployment ---
echo "🔧 [3/3] Applying Configuration..."
cd "$ANSIBLE_DIR"

# letsgooo
ansible-playbook ./playbooks/node-configure.yml \
  --vault-password-file "$VAULT_PASS_FILE"

echo ""
echo "🎉 DEPLOYMENT SUCCESSFUL!"
echo "   Nodes Deployed: ${ALL_IPS[*]}"
