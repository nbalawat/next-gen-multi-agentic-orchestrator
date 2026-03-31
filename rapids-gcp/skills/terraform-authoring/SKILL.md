---
name: terraform-authoring
description: "Implement phase: Write production-ready Terraform modules and configurations per feature spec, following GCP best practices and organizational standards"
---

# Terraform Authoring

This skill activates during the **implement phase** to write Terraform HCL code that realizes the planned module specifications.

## When to Use

Trigger this skill when:
- Module specs are ready and Terraform code needs to be written
- Existing Terraform modules need modification or extension
- Writing Terraform tests or validation logic

## Responsibilities

1. **Module Implementation** -- Write Terraform modules with properly typed variables, locals, resources, data sources, and outputs. Follow the `templates/terraform-module.tf` scaffold.

2. **Best Practices** -- Apply GCP and Terraform best practices:
   - Use `for_each` over `count` for collections
   - Tag all resources with standard labels (environment, team, cost-center)
   - Use data sources to reference existing infrastructure
   - Keep provider configuration in root modules only

3. **Validation** -- Add variable validation blocks, preconditions, and postconditions where appropriate. Write `terraform validate` and `terraform plan` checks.

4. **Documentation** -- Include inline comments for non-obvious logic. Generate module documentation via terraform-docs.

## Output

Production-ready `.tf` files organized by module, ready for review and deployment via the gcp-deploy skill.
