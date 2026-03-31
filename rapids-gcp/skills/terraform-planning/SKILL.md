---
name: terraform-planning
description: "Plan phase: Convert approved GCP architecture designs into detailed Terraform module specifications with dependency graphs and variable contracts"
---

# Terraform Planning

This skill activates during the **plan phase** to convert an approved GCP architecture into actionable Terraform module specifications.

## When to Use

Trigger this skill when:
- An architecture design has been approved and needs to be broken into Terraform modules
- You need to define module boundaries, input/output contracts, and dependency order
- Planning state management strategy (backends, workspaces, state locking)

## Responsibilities

1. **Module Decomposition** -- Break the architecture into reusable Terraform modules (e.g., networking, iam, compute, storage, monitoring). Each module should have a single responsibility.

2. **Variable Contracts** -- Define input variables and output values for each module. Specify types, defaults, validation rules, and descriptions.

3. **Dependency Graph** -- Document inter-module dependencies and the correct apply order. Identify resources that can be provisioned in parallel.

4. **State Strategy** -- Recommend state backend configuration (GCS bucket), workspace strategy, and state locking approach.

5. **Provider Pinning** -- Specify required provider versions and required Terraform version constraints.

## Output

Produce a set of module specification documents that the terraform-authoring skill can consume during the implement phase.
