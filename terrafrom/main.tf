terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.3.0"
}

provider "aws" {
  region = var.aws_region
}

module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  version = "4.0.0"

  name = "devops-vpc"
  cidr = "10.0.0.0/16"

  azs             = slice(data.aws_availability_zones.available.names, 0, 2)
  public_subnets  = ["10.0.1.0/24","10.0.2.0/24"]
  private_subnets = ["10.0.10.0/24","10.0.11.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.0.0"

  cluster_name    = "devops-eks"
  cluster_version = "1.27"
  vpc_id = module.vpc.vpc_id
  subnets = module.vpc.private_subnets

  node_groups = {
    nodes = {
      desired_capacity = 2
      max_capacity = 3
      min_capacity = 1
      instance_type = "t3.medium"
    }
  }
}

resource "aws_db_instance" "itemsdb" {
  allocated_storage    = 20
  engine               = "mysql"
  engine_version       = "8.0"
  instance_class       = "db.t3.micro"
  name                 = var.db_name
  username             = var.db_user
  password             = var.db_password
  skip_final_snapshot  = true
  publicly_accessible  = false
  vpc_security_group_ids = [module.vpc.default_security_group_id]
  db_subnet_group_name = aws_db_subnet_group.db_subnets.name
}

resource "aws_db_subnet_group" "db_subnets" {
  name       = "items-db-subnet"
  subnet_ids = module.vpc.private_subnets
  tags = { Name = "items-db-subnet" }
}

output "kubeconfig" {
  value = module.eks.kubeconfig
  sensitive = true
}

output "db_endpoint" {
  value = aws_db_instance.itemsdb.endpoint
}
