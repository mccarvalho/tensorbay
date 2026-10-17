variable "name_prefix" {
  description = "Prefix for resource names (e.g., neocloud-dev)."
  type        = string
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default     = {}
}
