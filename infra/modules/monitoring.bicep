// Log Analytics + workspace-based Application Insights.
// Daily cap keeps ingestion inside the 5 GB/month free allowance.
param prefix string
param location string
param tags object

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${prefix}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: json('0.15') }
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${prefix}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: law.id
    DisableLocalAuth: false
  }
}

output workspaceId string = law.id
output workspaceCustomerId string = law.properties.customerId
#disable-next-line outputs-should-not-contain-secrets // connection string is stored in Key Vault, not logged
output appInsightsConnectionString string = appi.properties.ConnectionString
output appInsightsName string = appi.name
