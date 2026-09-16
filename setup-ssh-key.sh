# Commands to run on the droplet console

# 1. Create .ssh directory if it doesn't exist
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# 2. Add your SSH public key to authorized_keys
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPBLuAOksnavoY+4m9qgjLd9oNdNFNsFztZdx13tYVG/ github-deploy" >> ~/.ssh/authorized_keys

# 3. Set correct permissions
chmod 600 ~/.ssh/authorized_keys

# 4. Verify the key was added
echo "✅ SSH key added! Contents of authorized_keys:"
cat ~/.ssh/authorized_keys
