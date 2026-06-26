# Incident Card Schema

Incident Cards are Markdown files containing exactly one fenced `yaml` or `yml` block with a top-level
`incident_card` key.

## Fields

| Field | Type | Required | Rule |
|---|---|---|---|
| `schema_version` | literal `1` | always | Must be `1`. |
| `id` | string | always | Matches `^INC-\d{4}-\d{3,}$`. |
| `status` | enum | always | `detected`, `mitigated`, or `resolved`. |
| `title` | string | always | 10 to 200 characters. |
| `severity` | enum | always | `low`, `medium`, `high`, or `critical`. |
| `environment` | enum | always | `production`, `staging`, `dev`, or `test`. |
| `service` | string | always | Lowercase kebab-case and listed in `allowed_services`. |
| `commander` | string/null | high, critical | GitHub login with `@`. |
| `detected_at` | aware datetime | always | Not later than the command clock plus 300 seconds. |
| `mitigated_at` | aware datetime/null | mitigated, resolved | Not earlier than `detected_at`. |
| `resolved_at` | aware datetime/null | resolved | Not earlier than `detected_at` or `mitigated_at`. |
| `description` | string | always | 20 to 5000 characters. |
| `impact` | string/null | high, critical, resolved | 20 to 5000 characters when present. |
| `mitigation` | string/null | mitigated, resolved | 20 to 5000 characters when present. |
| `root_cause` | string/null | resolved | 20 to 5000 characters when present. |
| `postmortem_link` | URL/null | optional | Valid URL. |
| `logs` | string/null | critical | 1 to 20000 characters when present. |

## Status Rules

| Status | Rules |
|---|---|
| `detected` | `resolved_at` must be null. `mitigated_at`, `mitigation`, and `root_cause` may be null. |
| `mitigated` | `mitigated_at` and `mitigation` are required. `resolved_at` must be null. |
| `resolved` | `resolved_at`, `impact`, `mitigation`, and `root_cause` are required. |

## Severity Rules

| Severity | Rules |
|---|---|
| `low` | `commander`, `impact`, and `logs` are optional unless required by status. |
| `medium` | `commander`, `impact`, and `logs` are optional unless required by status. |
| `high` | `commander` and `impact` are required. `logs` is optional. |
| `critical` | `commander`, `impact`, and `logs` are required. |

## Detected Example

```yaml
incident_card:
  schema_version: 1
  id: INC-2026-001
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
  logs: "https://logs.example.com/query/incident-2026-001"
```

## Mitigated Example

```yaml
incident_card:
  schema_version: 1
  id: INC-2026-002
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
  logs: "https://logs.example.com/query/incident-2026-002"
```

## Resolved Example

```yaml
incident_card:
  schema_version: 1
  id: INC-2026-003
  status: resolved
  title: Order API queue saturation
  severity: critical
  environment: production
  service: order-api
  commander: "@bob"
  detected_at: "2026-01-17T08:10:00Z"
  mitigated_at: "2026-01-17T08:40:00Z"
  resolved_at: "2026-01-17T09:05:00Z"
  description: "Order API queue saturation delayed order confirmation processing."
  impact: "Order confirmation emails and status updates were delayed for customers."
  mitigation: "Scaled queue workers and drained the backlog to normal operating levels."
  root_cause: "A deployment reduced worker concurrency for the order confirmation queue."
  postmortem_link: "https://example.com/postmortems/inc-2026-003"
  logs: "https://logs.example.com/query/incident-2026-003"
```

## Invalid Examples

Missing `incident_card`:

```yaml
schema_version: 1
id: INC-2026-004
```

Critical incident without `logs`:

```yaml
incident_card:
  schema_version: 1
  id: INC-2026-004
  status: detected
  title: Payment API outage
  severity: critical
  environment: production
  service: payment-api
  commander: "@alice"
  detected_at: "2026-01-15T08:10:00Z"
  description: "Payment API returned elevated errors for checkout requests."
  impact: "Checkout payments failed for customers using card payment methods."
  logs: null
```
