from base.cloud_service import CloudServiceComponent
import pulumi
import pulumi_azure as azure
import pulumi_azure_native as azure_native
import pulumi_command as command

class AzureComponent(CloudServiceComponent):
    def __init__(self, config):
        # Get config values
        self.config = config        


    def create_key_vault(self):
        # Logic for accessing secrets from Azure Key Vault
        key_vault_name = self.config.get("key_vault_name")
        subscription_id = self.config.get("subscription_id")
        resource_group_name = self.config.get("resource_group_name")

        key_vault_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.KeyVault/vaults/{key_vault_name}"

        # Get secrets from Key Vault
        admin_username = azure.keyvault.get_secret(name="adminUsername", key_vault_id=key_vault_id).value
        admin_password = azure.keyvault.get_secret(name="adminPassword", key_vault_id=key_vault_id).value

        self.admin_username = admin_username
        self.admin_password = admin_password


    def create_network(self):
        # Logic for creating a Virtual         
        appname = pulumi.get_project()
        location = self.config.get("location")
        resource_group_name = self.config.get("resource_group_name")

        virtual_network = azure_native.network.VirtualNetwork("virtualNetwork",
            address_space={
                "addressPrefixes": ["10.0.0.0/16"],
            },
            location=location,
            resource_group_name=resource_group_name,
            virtual_network_name=f"{appname}-azure-vn")

        subnet = azure_native.network.Subnet("subnet",
            address_prefix="10.0.0.0/16",
            resource_group_name=resource_group_name,
            subnet_name=f"{appname}-azure-sn",
            virtual_network_name=virtual_network.name)

        self.subnet_id = subnet.id

        # Logic for creating a Public IP Address
        location = self.config.get("location")
        resource_group_name = self.config.get("resource_group_name")

        public_ip = azure_native.network.PublicIPAddress(f"publicIP-azure",
            resource_group_name=resource_group_name,
            location=location,
            public_ip_allocation_method="Dynamic")

        self.public_ip_id = public_ip.id

    
    def create_instance(self):
        # Logic for creating an Azure VM
        env = pulumi.get_stack()
        appname = pulumi.get_project()
        location = self.config.get("location")
        resource_group_name = self.config.get("resource_group_name")

        network_interface = azure_native.network.NetworkInterface("networkInterface-" + env,
            resource_group_name=resource_group_name,
            location=location,
            ip_configurations=[{
                "name": "ipconfig1",
                "subnet": azure_native.network.SubnetArgs(
                    id=self.subnet_id,
                ),
                "public_ip_address": azure_native.network.PublicIPAddressArgs(
                    id=self.public_ip_id,
                ),
            }]
        )

        vm = azure.compute.LinuxVirtualMachine(f"nginxReverseProxyVM-azure",
            resource_group_name=resource_group_name,
            location=location,
            network_interface_ids=[network_interface.id],
            size="Standard_B1s",
            disable_password_authentication=False, 
            admin_username=self.admin_username,
            admin_password=self.admin_password,
            os_disk=azure.compute.LinuxVirtualMachineOsDiskArgs(
                storage_account_type="Standard_LRS",
                caching="ReadWrite",
                disk_size_gb=30,
            ),
            source_image_reference=azure.compute.LinuxVirtualMachineSourceImageReferenceArgs(
                publisher="Canonical",
                offer="0001-com-ubuntu-server-jammy",
                sku="22_04-lts",
                version="latest",
            ),
            tags={"Environment": azure}
        )

        self.vm_public_ip_address = vm.public_ip_address

        # Logic for configuring Nginx on the VM
        execute_script = command.remote.Command("executeNginxScript",
            connection=command.remote.ConnectionArgs(
                host=self.vm_public_ip_address,
                user=self.admin_username,
                password=self.admin_password,
            ),
            create="""
            sudo apt-get update -y
            sudo apt-get install -y nginx

            sudo bash -c 'cat > /etc/nginx/sites-available/default' << 'EOF'
            server {
                listen 80;
                server_name localhost;
                root /var/www/html;
                index index.html index.htm index.nginx-debian.html;
                location / {
                    try_files $uri $uri/ =404;
                }
            }
            server {
                listen 80;
                location / {
                    proxy_pass http://localhost;
                    proxy_set_header Host $host;
                    proxy_set_header X-Real-IP $remote_addr;
                    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                    proxy_set_header X-Forwarded-Proto $scheme;
                }
            }
            EOF
            sudo systemctl restart nginx
            """,
            opts=pulumi.ResourceOptions(replace_on_changes=[])
        )