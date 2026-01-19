# Auto-lookup latest EKS optimized AMIs by architecture
# AMI naming pattern: amazon-eks-node-al2023-{arch}-{type}-{eks_version}-v{date}

data "amazon-ami" "x86" {
  filters = {
    name                = "amazon-eks-node-al2023-x86_64-standard-${var.eks_version}-*"
    root-device-type    = "ebs"
    virtualization-type = "hvm"
    state               = "available"
  }
  owners      = ["amazon"]
  most_recent = true
  region      = var.region
}

data "amazon-ami" "arm64" {
  filters = {
    name                = "amazon-eks-node-al2023-arm64-standard-${var.eks_version}-*"
    root-device-type    = "ebs"
    virtualization-type = "hvm"
    state               = "available"
  }
  owners      = ["amazon"]
  most_recent = true
  region      = var.region
}
