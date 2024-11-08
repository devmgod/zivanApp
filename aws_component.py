from base.cloud_service import CloudServiceComponent
import pulumi
import pulumi_aws as aws
import os
class AWSComponent(CloudServiceComponent):
    def __init__(self, config):
        # Get config values
        self.config = config


    def create_key_vault(self):
        # Logic for creating an EC2 key pair
        appname = pulumi.get_project()

        # Read the public key from the file
        with open('.ssh/my-ec2-keypair.pub', 'r') as pub_key_file:
            public_key = pub_key_file.read()

        key_pair = aws.ec2.KeyPair("myKeyPair",
            key_name=f"{appname}-aws-keypair",
            public_key=public_key
        )

        self.key_name = key_pair.key_name


    def create_network(self):
        # Logic for creating a Security Group
        security_group = aws.ec2.SecurityGroup(
            "web-secgrp",
            description="Allow HTTP and SSH inbound traffic",
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    protocol="tcp",
                    from_port=80,
                    to_port=80,
                    cidr_blocks=["0.0.0.0/0"],
                    description="Allow HTTP traffic",
                ),
                aws.ec2.SecurityGroupIngressArgs(
                    protocol="tcp",
                    from_port=22,
                    to_port=22,
                    cidr_blocks=["0.0.0.0/0"],
                    description="Allow SSH traffic",
                ),
            ],
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    cidr_blocks=["0.0.0.0/0"],
                    description="Allow all outbound traffic"
                )
            ]
        )
        self.security_group_id = security_group.id


    def create_instance(self):
        # Logic for creating an EC2 instance        
        appname = pulumi.get_project()

        ami = "ami-04a81a99f5ec58529"  # Ubuntu AMI ID, replace with your preferred AMI
        instance_type = "t2.micro"     # Example instance type, replace as needed

        user_data_script = """#!/bin/bash
        # Update and install Nginx
        sudo apt-get update -y
        sudo apt-get install -y nginx

        # Create Nginx configuration file
        sudo bash -c 'cat > /etc/nginx/sites-available/default' << EOF
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
        """

        instance = aws.ec2.Instance("my-instance",
            ami=ami,
            instance_type=instance_type,
            vpc_security_group_ids=[self.security_group_id],
            key_name=self.key_name,
            associate_public_ip_address=True,  # Associate a public IP address with the instance
            tags={"Name": f"{appname}-aws-vm"},
            user_data=user_data_script  # Adding user data to configure Nginx
        )

        self.public_ip = instance.public_ip