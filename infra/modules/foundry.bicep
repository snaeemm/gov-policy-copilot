// Microsoft Foundry: one AI Services resource + project with a catalog of models for
// side-by-side comparison (OpenAI GPT, Microsoft Phi, Meta Llama, Mistral)
// Chosen by what has quota in UAE North (DeepSeek has 0 quota there).
// Pay-per-token GlobalStandard deployments: no cost unless called.
// Keyless: local auth disabled, access via Entra ID RBAC (Azure AI User).

param prefix string
param location string
param tags object
param developerPrincipalId string = ''
@description('Managed identity / CI principals that call the models')
param servicePrincipalIds array = []

@description('Azure AI Search service name (existing) to connect to the project for Foundry Agent Service')
param searchServiceName string = ''

@description('Models to deploy for comparison. capacity = thousands of tokens per minute (OpenAI) or units (others).')
param models array = [
  { name: 'gpt-5-mini', format: 'OpenAI', model: 'gpt-5-mini', version: '2025-08-07', capacity: 50 }
  { name: 'gpt-5-nano', format: 'OpenAI', model: 'gpt-5-nano', version: '2025-08-07', capacity: 50 }
  { name: 'gpt-5.4-mini', format: 'OpenAI', model: 'gpt-5.4-mini', version: '2026-03-17', capacity: 50 }
  { name: 'Phi-4', format: 'Microsoft', model: 'Phi-4', version: '7', capacity: 20 }
  { name: 'Llama-3.3-70B-Instruct', format: 'Meta', model: 'Llama-3.3-70B-Instruct', version: '9', capacity: 20 }
]

var suffix = uniqueString(resourceGroup().id)
var accountName = 'aif-${prefix}-${suffix}'

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: accountName
    allowProjectManagement: true
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: 'proj-${prefix}'
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'Gov Policy Copilot'
    description: 'Model comparison, evaluation and agent experiments for the Gov Policy Copilot'
  }
}

// Deployments on one account must be created one at a time.
@batchSize(1)
resource deployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [for m in models: {
  parent: foundry
  name: m.name
  sku: { name: 'GlobalStandard', capacity: m.capacity }
  properties: {
    model: { format: m.format, name: m.model, version: m.version }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
  dependsOn: [ project ]
}]

// Project connection to the existing Azure AI Search index (keyless; project identity reads it).
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' existing = if (!empty(searchServiceName)) {
  name: empty(searchServiceName) ? 'none' : searchServiceName
}

resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = if (!empty(searchServiceName)) {
  parent: project
  name: 'search-gov-policies'
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${searchServiceName}.search.windows.net'
    authType: 'AAD'
    isSharedToAll: true
    metadata: { ApiType: 'Azure', ResourceId: search.id, location: location }
  }
}

var searchIndexReader = '1407120a-92aa-4202-b7e9-c0e197c71c8f' // Search Index Data Reader
var searchServiceContributor = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'

resource projectSearchRead 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(searchServiceName)) {
  name: guid(search.id, project.id, searchIndexReader)
  scope: search
  properties: { principalId: project.identity.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexReader) }
}
resource projectSearchSvc 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(searchServiceName)) {
  name: guid(search.id, project.id, searchServiceContributor)
  scope: search
  properties: { principalId: project.identity.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributor) }
}

var azureAiUser = '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Azure AI User

resource devRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(developerPrincipalId)) {
  name: guid(foundry.id, developerPrincipalId, azureAiUser)
  scope: foundry
  properties: { principalId: developerPrincipalId, principalType: 'User', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureAiUser) }
}

resource svcRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for p in servicePrincipalIds: {
  name: guid(foundry.id, p, azureAiUser)
  scope: foundry
  properties: { principalId: p, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureAiUser) }
}]

output foundryName string = foundry.name
output foundryEndpoint string = 'https://${accountName}.services.ai.azure.com/'
output openAiCompatibleEndpoint string = 'https://${accountName}.openai.azure.com/'
output projectEndpoint string = 'https://${accountName}.services.ai.azure.com/api/projects/${project.name}'
output searchConnectionName string = empty(searchServiceName) ? '' : searchConnection.name
output modelDeployments array = [for m in models: m.name]
