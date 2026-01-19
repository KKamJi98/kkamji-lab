variable "region" {
  type    = string
  default = "ap-northeast-2"
}

variable "eks_version" {
  type    = string
  default = "1.34"
}

variable "ssh_username" {
  type    = string
  default = "ec2-user"
}

variable "subnet_id" {
  type    = string
  default = "subnet-00639976eab5efe78" # kkamji-dev-vpc-pub-a
}

variable "security_group_id" {
  type    = string
  default = "sg-0bc72092691a182f7" # kkamji-test-sg
}

variable "iam_instance_profile" {
  type    = string
  default = "kkamji-packer-test" # kkamji-packer-instance-profile
}

variable "instance_type_x86" {
  type    = string
  default = "t3.small"
}

variable "instance_type_arm64" {
  type    = string
  default = "t4g.small"
}
