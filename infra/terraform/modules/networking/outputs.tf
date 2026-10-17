output "vpc_id" {
  description = "VPC ID."
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "VPC CIDR block."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "Public subnet IDs."
  value       = aws_subnet.public[*].id
}

output "app_subnet_ids" {
  description = "Private application subnet IDs."
  value       = aws_subnet.app[*].id
}

output "data_subnet_ids" {
  description = "Private data subnet IDs."
  value       = aws_subnet.data[*].id
}

output "alb_security_group_id" {
  description = "ALB security group ID."
  value       = aws_security_group.alb.id
}

output "ecs_security_group_id" {
  description = "ECS tasks security group ID."
  value       = aws_security_group.ecs.id
}

output "aurora_security_group_id" {
  description = "Aurora security group ID."
  value       = aws_security_group.aurora.id
}

output "redis_security_group_id" {
  description = "Redis security group ID."
  value       = aws_security_group.redis.id
}
