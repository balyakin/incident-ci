# Valid detected card

```yaml
incident_card:
  schema_version: 1
  id: INC-2026-101
  status: detected
  title: Payment API latency spike
  severity: high
  environment: production
  service: payment-api
  commander: "@alice"
  detected_at: "2026-01-15T08:10:00Z"
  mitigated_at: null
  resolved_at: null
  description: "Payment API latency exceeded the SLO for checkout requests."
  impact: "Checkout requests were delayed for users in the EU region."
  mitigation: null
  root_cause: null
  postmortem_link: null
  logs: "https://logs.example.com/query/incident-2026-101"
```
