build {
  sources = [
    "source.amazon-ebs.x86",
    "source.amazon-ebs.arm64",
  ]

  provisioner "shell" {
    script = "${path.root}/scripts/bootstrap.sh"
    execute_command = "sudo -E bash '{{ .Path }}'"
  }
}
