# RDS PostgreSQL (single AZ dev)

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-db-subnet"
  subnet_ids = [aws_subnet.data.id, aws_subnet.data_secondary.id]

  tags = { Name = "${var.project_name}-${var.environment}-db-subnet-group" }
}

resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# DB credentials are now managed in secrets.tf as neocloud/{env}/db/master

resource "aws_db_instance" "main" {
  identifier = "${var.project_name}-${var.environment}"

  engine         = "postgres"
  engine_version = "16.15"
  instance_class = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = "neocloud"
  password = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az            = false # Single AZ for dev
  publicly_accessible = false

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  skip_final_snapshot       = true # Dev only
  final_snapshot_identifier = "${var.project_name}-${var.environment}-final"

  performance_insights_enabled = true

  tags = { Name = "${var.project_name}-${var.environment}-postgres" }
}
