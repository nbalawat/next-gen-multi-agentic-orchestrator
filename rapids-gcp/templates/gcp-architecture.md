# GCP Architecture Document

## Project Overview

- **Project Name**: [PROJECT_NAME]
- **GCP Project ID**: [PROJECT_ID]
- **Primary Region**: [REGION]
- **Environment**: [dev | staging | production]

## Requirements Summary

### Functional Requirements
- [ ] [Requirement 1]
- [ ] [Requirement 2]

### Non-Functional Requirements
- **Availability Target**: [e.g., 99.9%]
- **Latency Target**: [e.g., p99 < 200ms]
- **Throughput**: [e.g., 1000 RPS]
- **Data Residency**: [e.g., US only]

## Service Selection

| Component | GCP Service | Justification |
|-----------|-------------|---------------|
| Compute   | [Service]   | [Reason]      |
| Database  | [Service]   | [Reason]      |
| Storage   | [Service]   | [Reason]      |
| Messaging | [Service]   | [Reason]      |

## Network Topology

### VPC Design
- **VPC Name**: [NAME]
- **Subnets**:
  - [SUBNET_NAME]: [CIDR] ([REGION])

### Firewall Rules
| Rule Name | Direction | Source | Target | Ports | Action |
|-----------|-----------|--------|--------|-------|--------|
| [NAME]    | [INGRESS/EGRESS] | [SOURCE] | [TARGET] | [PORTS] | [ALLOW/DENY] |

### Load Balancing
- **Type**: [Global HTTP(S) / Regional / Internal]
- **Backend Services**: [LIST]

## IAM Design

### Service Accounts
| Service Account | Purpose | Roles |
|----------------|---------|-------|
| [SA_NAME]@[PROJECT].iam | [PURPOSE] | [ROLES] |

### Custom Roles
- [ROLE_NAME]: [PERMISSIONS]

## Cost Estimation

| Service | Configuration | Monthly Estimate |
|---------|--------------|-----------------|
| [SERVICE] | [CONFIG] | $[AMOUNT] |
| **Total** | | **$[TOTAL]** |

### Optimization Opportunities
- [ ] Committed Use Discounts
- [ ] Sustained Use Discounts
- [ ] Preemptible/Spot VMs for batch workloads

## Architecture Decisions

### ADR-001: [Decision Title]
- **Status**: [Proposed | Accepted | Deprecated]
- **Context**: [Why this decision is needed]
- **Decision**: [What was decided]
- **Consequences**: [Trade-offs and implications]

## Diagram

```
[ASCII architecture diagram or reference to diagram file]
```
