# ECS Fargate Cluster + Service

resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = { Name = "${var.project_name}-${var.environment}-cluster" }
}

# ECR Repository
resource "aws_ecr_repository" "api" {
  name                 = "${var.project_name}-api"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # Dev only

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = "${var.project_name}-${var.environment}-ecr" }
}

# ECS Task Execution Role
resource "aws_iam_role" "ecs_execution" {
  name = "${var.project_name}-${var.environment}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "secrets-access"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.db_master.arn,
        aws_secretsmanager_secret.app_config.arn,
        aws_secretsmanager_secret.cognito.arn,
        aws_secretsmanager_secret.infra_config.arn,
      ]
    }]
  })
}

# ECS Task Role (app permissions)
resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-${var.environment}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task" {
  name = "app-permissions"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "events:PutEvents"
        ]
        Resource = [aws_cloudwatch_event_bus.main.arn]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.documents.arn,
          "${aws_s3_bucket.documents.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [aws_secretsmanager_secret.db_credentials.arn]
      }
    ]
  })
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project_name}-${var.environment}/api"
  retention_in_days = 30

  tags = { Name = "${var.project_name}-${var.environment}-api-logs" }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project_name}-${var.environment}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_cpu
  memory                   = var.ecs_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "api"
    image = var.app_image != "" ? var.app_image : "${aws_ecr_repository.api.repository_url}:latest"

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]

    # Non-secret config only — all credentials come from Secrets Manager
    environment = [
      { name = "APP_ENV",    value = var.environment },
      { name = "AWS_REGION", value = var.aws_region },
    ]

    # All secrets loaded from Secrets Manager at task startup
    secrets = [
      { name = "DATABASE_URL",        valueFrom = "${aws_secretsmanager_secret.db_master.arn}:url::" },
      { name = "REDIS_URL",           valueFrom = "${aws_secretsmanager_secret.infra_config.arn}:redis_url::" },
      { name = "AWS_EVENTBRIDGE_BUS", valueFrom = "${aws_secretsmanager_secret.infra_config.arn}:eventbridge_bus::" },
      { name = "AWS_S3_BUCKET",       valueFrom = "${aws_secretsmanager_secret.infra_config.arn}:s3_bucket::" },
      { name = "JWT_SECRET_KEY",      valueFrom = "${aws_secretsmanager_secret.app_config.arn}:jwt_secret_key::" },
      { name = "JWT_ALGORITHM",       valueFrom = "${aws_secretsmanager_secret.app_config.arn}:jwt_algorithm::" },
      { name = "APP_DEBUG",           valueFrom = "${aws_secretsmanager_secret.app_config.arn}:app_debug::" },
      { name = "CORS_ORIGINS",        valueFrom = "${aws_secretsmanager_secret.app_config.arn}:cors_origins::" },
      { name = "COGNITO_USER_POOL_ID",valueFrom = "${aws_secretsmanager_secret.cognito.arn}:user_pool_id::" },
      { name = "COGNITO_CLIENT_ID",   valueFrom = "${aws_secretsmanager_secret.cognito.arn}:client_id::" },
      { name = "COGNITO_REGION",      valueFrom = "${aws_secretsmanager_secret.cognito.arn}:region::" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])
}

# Database URL secret is now managed in secrets.tf as neocloud/{env}/db/master

# ECS Service
resource "aws_ecs_service" "api" {
  name            = "${var.project_name}-${var.environment}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.ecs_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.private.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.https]
}
