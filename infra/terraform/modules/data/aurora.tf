########################################
# Aurora PostgreSQL (Serverless v2)
########################################

resource "aws_db_subnet_group" "aurora" {
  name       = "${var.name_prefix}-aurora-subnets"
  subnet_ids = var.data_subnet_ids
  tags       = var.tags
}

resource "aws_rds_cluster" "aurora" {
  cluster_identifier = "${var.name_prefix}-aurora"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = var.aurora_engine_version
  database_name      = var.aurora_database_name
  master_username    = var.aurora_master_username
  master_password    = var.aurora_master_password

  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [var.aurora_security_group_id]

  storage_encrypted = true
  kms_key_id        = var.kms_rds_key_arn

  backup_retention_period      = 7
  preferred_backup_window      = "03:00-04:00"
  preferred_maintenance_window = "sun:04:30-sun:05:30"

  # For dev: allow destroy without a final snapshot. Set to false for prod.
  skip_final_snapshot       = true
  final_snapshot_identifier = "${var.name_prefix}-aurora-final"
  deletion_protection       = false

  enabled_cloudwatch_logs_exports = ["postgresql"]

  serverlessv2_scaling_configuration {
    min_capacity = var.aurora_min_capacity
    max_capacity = var.aurora_max_capacity
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [master_password]
  }
}

resource "aws_rds_cluster_instance" "aurora" {
  count              = 1
  identifier         = "${var.name_prefix}-aurora-${count.index}"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora.engine
  engine_version     = aws_rds_cluster.aurora.engine_version

  db_subnet_group_name = aws_db_subnet_group.aurora.name

  performance_insights_enabled = true
  tags                         = var.tags
}
