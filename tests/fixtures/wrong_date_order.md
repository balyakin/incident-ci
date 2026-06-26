# Wrong date order

```yaml
incident_card:
  schema_version: 1
  id: INC-2026-104
  status: resolved
  title: Order API queue saturation
  severity: high
  environment: production
  service: order-api
  commander: "@bob"
  detected_at: "2026-01-17T08:10:00Z"
  mitigated_at: "2026-01-17T08:40:00Z"
  resolved_at: "2026-01-17T08:05:00Z"
  description: "Order API queue saturation delayed order confirmation processing."
  impact: "Order confirmation emails and status updates were delayed for customers."
  mitigation: "Scaled queue workers and drained the backlog to normal operating levels."
  root_cause: "A deployment reduced worker concurrency for the order confirmation queue."
  postmortem_link: "https://example.com/postmortems/inc-2026-104"
  logs: "https://logs.example.com/query/incident-2026-104"
```
