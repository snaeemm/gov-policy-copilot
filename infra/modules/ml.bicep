// Azure Machine Learning workspace used ONLY for MLflow experiment tracking + model registry.
// No compute clusters, no managed endpoints, no ACR (training runs on free GitHub runners;
// the model is served inside the existing Container App). Cost: storage only (~$0.05/month).
// Deploy standalone: az deployment group create -g rg-govcopilot-dev -f infra/modules/ml.bicep
param location string = resourceGroup().location
param prefix string = 'govcopilot-dev'
param tags object = { project: 'gov-policy-copilot', env: 'dev', costCenter: 'portfolio' }
param keyVaultName string = 'kv-gc-spemmlgtc6f7m'
param appInsightsName string = 'appi-govcopilot-dev'
@description('Principals (users / service principals) granted AzureML Data Scientist')
param dataScientistPrincipals array = []

var suffix = uniqueString(resourceGroup().id)
var dataScientistRole = 'f6c7c914-8db3-469d-8ca1-694a8f32e121'

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = { name: keyVaultName }
resource appi 'Microsoft.Insights/components@2020-02-02' existing = { name: appInsightsName }

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'stml${take(suffix, 18)}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource ws 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: 'mlw-${prefix}'
  location: location
  tags: tags
  sku: { name: 'Basic', tier: 'Basic' }
  identity: { type: 'SystemAssigned' }
  properties: {
    friendlyName: 'Gov Policy Copilot ML'
    description: 'MLflow tracking + model registry for the bilingual query classifier'
    storageAccount: storage.id
    keyVault: kv.id
    applicationInsights: appi.id
    publicNetworkAccess: 'Enabled'
  }
}

resource ds 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for p in dataScientistPrincipals: {
  name: guid(ws.id, p.id, dataScientistRole)
  scope: ws
  properties: {
    principalId: p.id
    principalType: p.type
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', dataScientistRole)
  }
}]

output workspaceName string = ws.name
output mlflowTrackingUri string = ws.properties.mlFlowTrackingUri
