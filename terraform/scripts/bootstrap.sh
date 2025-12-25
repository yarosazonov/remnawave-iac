#!/bin/bash
set -e

# Variable injected by Terraform
# The Automation User (Service Account)
ANSIBLE_USER="${ansible_username}"
ANSIBLE_SSH_KEY="${ansible_pub_key}"
ANSIBLE_ALLOWED_IP="${ansible_allowed_ip}"

# The Human Admin User
ADMIN_USER="${admin_username}"
ADMIN_SSH_KEY="${admin_pub_key}"

# 1. Update & Install Python, Sudo
apt-get update
apt-get install -y python3 sudo

setup_user() {
    local username="$1"
    local pubkey="$2"

    echo "Setting up user: $username"

    # Create user with home directory, bash shell, and add to sudo group
    useradd -m -s /bin/bash -G sudo "$username"

    # Create SSH directory structure
    mkdir -p "/home/$username/.ssh"

    # Inject Public Key
    echo "$pubkey" >> "/home/$username/.ssh/authorized_keys"

    # Set Permissions
    chmod 700 "/home/$username/.ssh"
    chmod 600 "/home/$username/.ssh/authorized_keys"
    chown -R "$username:$username" "/home/$username/.ssh"
}

setup_user "$ANSIBLE_USER" "$ANSIBLE_SSH_KEY"
setup_user "$ADMIN_USER" "$ADMIN_SSH_KEY"

# 4. Sudoers
echo "$ANSIBLE_USER ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$ANSIBLE_USER"
chmod 0440 "/etc/sudoers.d/$ANSIBLE_USER"

echo "$ADMIN_USER ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$ADMIN_USER"
chmod 0440 "/etc/sudoers.d/$ADMIN_USER"

# 5. Secure SSH - using the modular configuration approach
# Remove any existing cloud-init SSH configurations
rm -f /etc/ssh/sshd_config.d/*cloud*

# Create our own SSH security configuration file
cat > /etc/ssh/sshd_config.d/10-security.conf << EOF
# Disable password authentication
PasswordAuthentication no
# Disable root login
PermitRootLogin no
EOF

# --- SSH User Restriction (SSHD Level) ---
if [ -n "$ANSIBLE_ALLOWED_IP" ] && [ "$ANSIBLE_ALLOWED_IP" != "0.0.0.0/0" ]; then
    echo "🔐 Restricting SSH for user '$ANSIBLE_USER' to IP: $ANSIBLE_ALLOWED_IP"
    # Allow Admin from ANY, Ansible from IP
    echo "AllowUsers $ADMIN_USER $ANSIBLE_USER@$ANSIBLE_ALLOWED_IP" >> /etc/ssh/sshd_config.d/10-security.conf
else
    echo "🌍 Allowing SSH for '$ANSIBLE_USER' from ANY"
    # Allow both from ANY
    echo "AllowUsers $ADMIN_USER $ANSIBLE_USER" >> /etc/ssh/sshd_config.d/10-security.conf
fi

# Apply proper permissions
chmod 644 /etc/ssh/sshd_config.d/10-security.conf

# Disabling cloud-init to prevent SSH config resets
touch /etc/cloud/cloud-init.disabled

# Restart SSH service to apply changes
systemctl restart ssh