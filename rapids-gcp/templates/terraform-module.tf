# -----------------------------------------------------------------------------
# Module: [MODULE_NAME]
# Description: [MODULE_DESCRIPTION]
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }
}

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

variable "project_id" {
  description = "The GCP project ID"
  type        = string

  validation {
    condition     = length(var.project_id) > 0
    error_message = "project_id must not be empty."
  }
}

variable "region" {
  description = "The GCP region for resource deployment"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "The deployment environment (dev, staging, production)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "environment must be one of: dev, staging, production."
  }
}

variable "labels" {
  description = "Common labels to apply to all resources"
  type        = map(string)
  default     = {}
}

# -----------------------------------------------------------------------------
# Locals
# -----------------------------------------------------------------------------

locals {
  default_labels = merge(
    {
      environment = var.environment
      managed_by  = "terraform"
    },
    var.labels
  )
}

# -----------------------------------------------------------------------------
# Resources
# -----------------------------------------------------------------------------

# TODO: Add resources here

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "project_id" {
  description = "The GCP project ID"
  value       = var.project_id
}
