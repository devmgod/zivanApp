from base.cloud_service import CloudServiceComponent
import pulumi
import pulumi_gcp as gcp

class GCPComponent(CloudServiceComponent):
    def __init__(self, config):
        # Get config values
        self.config = config
        

    def create_key_vault(self):        
        # Read the public key from the file
        with open('.ssh/my-ec2-keypair.pub', 'r') as pub_key_file:
            public_key = pub_key_file.read().strip()
        self.public_key = public_key


    def create_network(self):
        # Logic for creating a Firewall rule to allow HTTP and SSH traffic
        firewall_rule = gcp.compute.Firewall("web-firewall",
            network="default",
            allows=[
                gcp.compute.FirewallAllowArgs(
                    protocol="tcp",
                    ports=["80"],
                ),
                gcp.compute.FirewallAllowArgs(
                    protocol="tcp",
                    ports=["22"],
                ),
            ],
            source_ranges=["0.0.0.0/0"],
            target_tags=["http-server", "ssh-server"]
        )        


    def create_instance(self):
        # Logic for creating a VM instance
        instance = gcp.compute.Instance("my-instance",
            machine_type="e2-medium",  # Example machine type
            zone="us-central1-a",
            boot_disk=gcp.compute.InstanceBootDiskArgs(
                initialize_params=gcp.compute.InstanceBootDiskInitializeParamsArgs(
                    image="ubuntu-minimal-2004-focal-v20240812",  # Example image
                ),
            ),
            network_interfaces=[gcp.compute.InstanceNetworkInterfaceArgs(
                network="default",
                access_configs=[gcp.compute.InstanceNetworkInterfaceAccessConfigArgs()],  # Allocate a new ephemeral public IP address
            )],
            metadata={
                "ssh-keys": f"ubuntu:{self.public_key}"  # Use the SSH public key
            },
            tags=["http-server", "ssh-server"],  # Tags to match firewall rules
            metadata_startup_script="""#!/bin/bash
            # Update and install Nginx
            sudo apt-get update -y
            sudo apt-get install -y nginx

            # Create Nginx configuration file
            sudo bash -c 'cat > /etc/nginx/sites-available/default' << 'EOF'
            server {
                listen 80;
                server_name localhost;
                root /var/www/html;
                index index.html index.htm index.nginx-debian.html;
                location / {
                    try_files \\$uri \\$uri/ =404;
                }
            }
            server {
                listen 80;
                location / {
                    proxy_pass http://localhost;
                    proxy_set_header Host \\$host;
                    proxy_set_header X-Real-IP \\$remote_addr;
                    proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;
                    proxy_set_header X-Forwarded-Proto \\$scheme;
                }
            }
            EOF

            # Restart Nginx to apply changes
            sudo systemctl restart nginx
            """,
        )

        self.instance_id = instance.id
        self.public_ip = instance.network_interfaces[0].access_configs[0].nat_ip
        self.private_ip = instance.network_interfaces[0].network_ip