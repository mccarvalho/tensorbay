output "aurora_cluster_endpoint" {
  description = "Aurora cluster writer endpoint."
  value       = aws_rds_cluster.aurora.endpoint
}

output "aurora_reader_endpoint" {
  description = "Aurora cluster reader endpoint."
  value       = aws_rds_cluster.aurora.reader_endpoint
}

output "aurora_port" {
  description = "Aurora port."
  value       = aws_rds_cluster.aurora.port
}

output "aurora_database_name" {
  description = "Aurora initial database name."
  value       = aws_rds_cluster.aurora.database_name
}

output "redis_primary_endpoint" {
  description = "Redis primary endpoint address."
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_reader_endpoint" {
  description = "Redis reader endpoint address."
  value       = aws_elasticache_replication_group.redis.reader_endpoint_address
}

output "redis_port" {
  description = "Redis port."
  value       = aws_elasticache_replication_group.redis.port
}
