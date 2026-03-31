---
name: gcp-architecture
description: "Analysis phase: Design GCP architecture including service selection, IAM design, network topology, and cost estimation for cloud-native applications"
---

# GCP Architecture Design

This skill activates during the **analysis phase** of a RAPIDS project to produce a comprehensive GCP architecture design.

## When to Use

Trigger this skill when the user is:
- Starting a new GCP project and needs architecture guidance
- Evaluating which GCP services to use for a workload
- Designing IAM roles, policies, and service accounts
- Planning VPC networks, subnets, and firewall rules
- Estimating infrastructure costs

## Responsibilities

1. **Service Selection** -- Recommend appropriate GCP services (Compute Engine, Cloud Run, GKE, Cloud Functions, etc.) based on workload requirements including latency, throughput, and cost constraints.

2. **IAM Design** -- Define least-privilege IAM roles, service accounts, and organization policies. Produce a role-binding matrix mapping identities to resources.

3. **Network Topology** -- Design VPC networks, subnets, Cloud NAT, Cloud Interconnect, and firewall rules. Document ingress/egress paths and private connectivity requirements.

4. **Cost Estimation** -- Provide rough cost estimates using GCP pricing, including committed use discounts and sustained use discounts where applicable.

## Output

Produce a structured architecture document using the `templates/gcp-architecture.md` template. The document should be ready for review before proceeding to the planning phase.
