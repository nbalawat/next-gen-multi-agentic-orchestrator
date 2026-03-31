---
name: cloud-monitoring
description: "Sustain phase: Configure Cloud Monitoring dashboards, alerting policies, SLOs, and uptime checks for ongoing operational health of GCP infrastructure"
---

# Cloud Monitoring

This skill activates during the **sustain phase** to set up and maintain observability for deployed GCP infrastructure.

## When to Use

Trigger this skill when:
- Infrastructure has been deployed and needs monitoring
- SLOs and error budgets need to be defined
- Alerting policies need to be created or tuned
- Dashboards need to be built for operational visibility

## Responsibilities

1. **Dashboard Creation** -- Build Cloud Monitoring dashboards with key metrics: CPU, memory, request latency, error rates, and custom application metrics.

2. **Alerting Policies** -- Configure alerting policies with appropriate thresholds, notification channels (PagerDuty, Slack, email), and escalation paths. Avoid alert fatigue by tuning sensitivity.

3. **SLO Definition** -- Define Service Level Objectives with:
   - SLI selection (availability, latency, throughput)
   - SLO targets (e.g., 99.9% availability)
   - Error budget tracking and burn-rate alerts

4. **Uptime Checks** -- Configure uptime checks for public endpoints with appropriate check intervals and regions.

5. **Log-Based Metrics** -- Create log-based metrics for application-specific signals not captured by default GCP metrics.

## Output

Monitoring configuration as Terraform resources (google_monitoring_*) and operational runbooks for common alert responses.
