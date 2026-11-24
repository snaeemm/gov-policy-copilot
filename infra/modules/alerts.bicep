// Azure Monitor log-search alert rules on the App Insights / Log Analytics data.
// COST: each scheduled query rule is billed per evaluation frequency (roughly $0.50/month per
// rule at 15-minute frequency, $1.50 at 5-minute). 5 rules at 15 min ≈ $2.50/month total.
// Action group email notifications are free (first 1,000/month). Disabled by default:
// main.bicep param deployAlerts = false.
param prefix string
param location string
param tags object
param appInsightsId string
param email string

resource ag 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-${prefix}'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: 'govcopilot'
    enabled: true
    emailReceivers: [ { name: 'owner', emailAddress: email, useCommonAlertSchema: true } ]
  }
}

var base = 'traces | where message == "copilot_request" | extend outcome = tostring(customDimensions.outcome)'

var rules = [
  {
    name: 'out-of-scope-spike'
    description: 'Out-of-scope rate above 40% over the last hour (min 20 requests) - possible corpus gap or planner regression'
    query: '${base} | summarize total = count(), oos = countif(outcome == "out_of_scope") | where total >= 20 | extend rate = 100.0 * oos / total | where rate > 40'
    severity: 3
  }
  {
    name: 'blocked-spike'
    description: 'Blocked (safety filter) rate above 20% over the last hour - possible attack or false-positive regression'
    query: '${base} | summarize total = count(), blocked = countif(outcome == "blocked") | where total >= 20 | extend rate = 100.0 * blocked / total | where rate > 20'
    severity: 2
  }
  {
    name: 'escalation-rate-high'
    description: 'Human-review escalation rate above 25% over the last hour - groundedness degradation'
    query: '${base} | summarize total = count(), esc = countif(outcome == "escalated") | where total >= 20 | extend rate = 100.0 * esc / total | where rate > 25'
    severity: 2
  }
  {
    name: 'latency-p95-high'
    description: 'p95 copilot latency above 45 s over the last hour'
    query: '${base} | summarize p95 = percentile(todouble(customDimensions.latency_ms), 95), total = count() | where total >= 10 and p95 > 45000'
    severity: 3
  }
  {
    name: 'daily-cost-high'
    description: 'Model cost above $1 in the last 24 h (budget guardrail on top of the $5 subscription budget)'
    query: '${base} | where timestamp > ago(24h) | summarize cost = sum(todouble(customDimensions.cost_usd)) | where cost > 1'
    severity: 2
  }
]

resource alerts 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = [for r in rules: {
  name: 'alert-${prefix}-${r.name}'
  location: location
  tags: tags
  properties: {
    displayName: r.name
    description: r.description
    severity: r.severity
    enabled: true
    scopes: [ appInsightsId ]
    evaluationFrequency: 'PT15M'
    windowSize: r.name == 'daily-cost-high' ? 'P1D' : 'PT1H'
    criteria: {
      allOf: [
        {
          query: r.query
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: { numberOfEvaluationPeriods: 1, minFailingPeriodsToAlert: 1 }
        }
      ]
    }
    actions: { actionGroups: [ ag.id ] }
    autoMitigate: true
  }
}]

output actionGroupId string = ag.id
