---
name: gcp-deploy
description: "Deploy phase: Execute Terraform apply, manage Cloud Run deployments, and coordinate GCP infrastructure provisioning with rollback safety"
---

# GCP Deploy

This skill activates during the **deploy phase** to provision infrastructure and deploy applications to GCP.

## When to Use

Trigger this skill when:
- Terraform code is reviewed and ready to apply
- Cloud Run services need to be deployed or updated
- Infrastructure changes need to be rolled out with safety checks

## Responsibilities

1. **Terraform Apply** -- Run `terraform plan` for review, then `terraform apply` with appropriate auto-approve settings based on environment (never auto-approve production).

2. **Cloud Run Deployment** -- Build container images, push to Artifact Registry, and deploy to Cloud Run with traffic splitting for canary releases.

3. **Rollback Safety** -- Maintain rollback capability:
   - Keep previous Terraform state versions in GCS
   - Use Cloud Run revisions for instant rollback
   - Document rollback procedures for each deployment

4. **Post-Deploy Validation** -- Run smoke tests and health checks after deployment. Verify DNS, SSL certificates, and connectivity.

## Output

Deployment report including provisioned resources, endpoints, and rollback instructions.
