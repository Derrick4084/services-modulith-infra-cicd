# E-Commerce Infrastructure Pipeline (AWS CDK)

This project contains the AWS CDK application responsible for deploying and managing the CI/CD infrastructure for the E-Commerce backend platform.

## Overview

The solution provisions an AWS CodePipeline that automatically monitors GitHub repositories for source code changes and deploys infrastructure updates through AWS CloudFormation.

The pipeline orchestrates the deployment of multiple infrastructure stacks including:

* **VPC Stack** – Networking, subnets, routing, and security configuration.
* **PostgreSQL Stack** – Amazon Aurora PostgreSQL database resources.
* **DocumentDB Stack** – Amazon DocumentDB cluster and related resources.
* **ECS Fargate Stack** – Containerized application services running on Amazon ECS Fargate.

## Pipeline Features

* GitHub source integration with automatic pipeline execution on push events.
* Independent CloudFormation deployment actions for each infrastructure stack.
* Environment-specific deployments:

  * **Development**
  * **Production**
* Manual approval stage required before production deployments.
* Automated CloudFormation stack creation and updates.
* Build and deployment notifications through Amazon SNS.
* Email subscriptions for stakeholders to receive:

  * Build status notifications
  * Deployment notifications
  * Production approval requests
  * Approval and deployment results

## Deployment Flow

1. Developer pushes changes to GitHub.
2. CodePipeline detects the update.
3. Pipeline validates and processes CloudFormation templates.
4. Individual CloudFormation deployment actions update the corresponding AWS stacks.
5. For production deployments, a manual approval stage must be completed before deployment continues.
6. Notifications are sent throughout the deployment lifecycle to subscribed recipients.

## Technologies

* AWS CDK (Python)
* AWS CodePipeline
* AWS CodeBuild
* AWS CloudFormation
* Amazon ECS Fargate
* Amazon Aurora PostgreSQL
* Amazon DocumentDB
* Amazon SNS
* GitHub Integration

## Goal

Provide a fully automated, repeatable, and secure deployment process for the E-Commerce platform infrastructure while maintaining separation between development and production environments and ensuring visibility through notifications and approval workflows.
