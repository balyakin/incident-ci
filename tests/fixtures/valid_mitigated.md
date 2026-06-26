# Valid mitigated card

```yaml
incident_card:
  schema_version: 1
  id: INC-2026-102
  status: mitigated
  title: Auth token refresh failures
  severity: medium
  environment: production
  service: auth-api
  commander: null
  detected_at: "2026-01-16T08:10:00Z"
  mitigated_at: "2026-01-16T08:40:00Z"
  resolved_at: null
  description: "Auth API returned intermittent errors while refreshing user tokens."
  impact: null
  mitigation: "Rolled back the refresh-token deployment and verified successful token refreshes."
  root_cause: null
  postmortem_link: null
  logs: "https://logs.example.com/query/incident-2026-102"
```
