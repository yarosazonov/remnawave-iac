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

# Check if user wants to DESTROY
MODE="apply" # Default mode

case "$1" in
    destroy)
        MODE="destroy"
        ;;
    "")
        ;;
    *)
        echo "❌ ERROR: Unknown argument '$1'"
        echo "Usage: $0 [destroy]"
        exit 1
        ;;
esac

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

# Sensitive vars
export VULTR_API_KEY="$VULTR_API_KEY"
export CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN"
export TF_VAR_PANEL_API_TOKEN="$PANEL_API_TOKEN"
export PANEL_CERT="$PANEL_CERT"

# Generate terraform variables file
cat > "$TF_DIR/deployment.auto.tfvars" <<EOF
cloudflare_zone      = "${CLOUDFLARE_ZONE}"
panel_api_url        = "${PANEL_API_URL}"
panel_ip             = "${PANEL_IP}"
config_profile_uuid  = "${CONFIG_PROFILE_UUID}"
active_inbounds      = ${ACTIVE_INBOUNDS}
node_api_port        = "${NODE_API_PORT}"
ansible_username     = "${ANSIBLE_USERNAME}"
ansible_key_path     = "${ANSIBLE_KEY_PATH}"
admin_username       = "${ADMIN_USERNAME}"
admin_key_path       = "${ADMIN_KEY_PATH}"
ansible_allowed_ip   = "${ANSIBLE_STATIC_SSH_IP}"
EOF

cd "$TF_DIR"

# Initializing
terraform init

# Check if user wants to DESTROY
if [ "$MODE" == "destroy" ]; then
    echo "🔥 DESTROY MODE ACTIVATED"
    echo "⚠️  WARNING: This will DESTROY all resources managed by Terraform."
    read -p "    Are you sure? (y/n) " -r
    if [[ ! $REPLY =~ ^[Yy](es)?$ ]]; then
        echo "🚫 Cancelled."
        exit 1
    fi
    terraform destroy
    echo "✅ Infrastructure destroyed."
    exit 0
fi

# This calculates the state changes and saves them to 'tfplan'
echo "📋 Generating Execution Plan..."
# Temporarily allow non-zero exit code for detailed-exitcode
set +e 
terraform plan -out=tfplan -detailed-exitcode
PLAN_EXIT_CODE=$?
set -e 

if [ $PLAN_EXIT_CODE -eq 0 ]; then
    echo "✅ No infrastructure changes detected."
    echo ""
elif [ $PLAN_EXIT_CODE -eq 2 ]; then
    # Changes detected, ask for approval
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
else
    # Exit code 1 means error
    echo "❌ Error generating Terraform plan."
    exit 1
fi

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
        if ssh -o BatchMode=yes -o ConnectTimeout=2 -o StrictHostKeyChecking=no -i "$ANSIBLE_KEY_PATH" "$ANSIBLE_USERNAME@$IP" "echo 'ready'" &>/dev/null; then
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
  -e "node_api_port=$NODE_API_PORT" \
  -e "panel_ip=$PANEL_IP" \
  -e "panel_cert=$PANEL_CERT" \
  -e "monitoring_ip=$MONITORING_IP"
echo ""
echo "🎉 DEPLOYMENT SUCCESSFUL!"
echo "   Nodes Deployed:"
for ip in "${ALL_IPS[@]}"; do
    echo "   - $ip"
done