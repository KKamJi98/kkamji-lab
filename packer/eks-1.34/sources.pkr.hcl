packer {
  required_plugins {
    amazon = {
      source  = "github.com/hashicorp/amazon"
      version = ">= 1.2.7"
    }
  }
}

locals {
  build_date  = formatdate("YYYYMMDD", timestamp())
  name_prefix = "custom-eks-${var.eks_version}-amazon-linux-2023"
  common_tags = {
    creater = "ethan.kim"
  }
}

source "amazon-ebs" "x86" {
  region               = var.region
  source_ami           = data.amazon-ami.x86.id
  instance_type        = var.instance_type_x86
  subnet_id            = var.subnet_id
  security_group_id    = var.security_group_id
  iam_instance_profile = var.iam_instance_profile
  communicator         = "ssh"
  ssh_interface        = "session_manager"
  ssh_username         = var.ssh_username
  pause_before_ssm     = "10s"
  ssh_timeout          = "3m"

  ami_name = "${local.name_prefix}-x86-v${local.build_date}"
  tags     = merge(local.common_tags, { Name = "${local.name_prefix}-x86-v${local.build_date}" })

  ami_block_device_mappings {
    device_name           = "/dev/xvda"
    volume_size           = 30
    volume_type           = "gp3"
    iops                  = 3000
    throughput            = 125
    delete_on_termination = true
    encrypted             = false
  }

  launch_block_device_mappings {
    device_name           = "/dev/xvda"
    volume_size           = 30
    volume_type           = "gp3"
    iops                  = 3000
    throughput            = 125
    delete_on_termination = true
    encrypted             = false
  }
}

source "amazon-ebs" "arm64" {
  region               = var.region
  source_ami           = data.amazon-ami.arm64.id
  instance_type        = var.instance_type_arm64
  subnet_id            = var.subnet_id
  security_group_id    = var.security_group_id
  iam_instance_profile = var.iam_instance_profile
  communicator         = "ssh"
  ssh_interface        = "session_manager"
  ssh_username         = var.ssh_username
  pause_before_ssm     = "10s"
  ssh_timeout          = "3m"

  ami_name = "${local.name_prefix}-arm64-v${local.build_date}"
  tags     = merge(local.common_tags, { Name = "${local.name_prefix}-arm64-v${local.build_date}" })

  ami_block_device_mappings {
    device_name           = "/dev/xvda"
    volume_size           = 30
    volume_type           = "gp3"
    iops                  = 3000
    throughput            = 125
    delete_on_termination = true
    encrypted             = false
  }

  launch_block_device_mappings {
    device_name           = "/dev/xvda"
    volume_size           = 30
    volume_type           = "gp3"
    iops                  = 3000
    throughput            = 125
    delete_on_termination = true
    encrypted             = false
  }
}
