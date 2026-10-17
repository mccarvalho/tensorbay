variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
}

variable "azs" {
  description = "List of Availability Zone names to use."
  type        = list(string)
}

variable "single_nat_gateway" {
  description = "Use a single NAT gateway instead of one per AZ."
  type        = bool
  default     = true
}

variable "container_port" {
  description = "Application container port, used for the ECS ingress rule from the ALB."
  type        = number
  default     = 8000
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default     = {}
}
