// Gov Policy Copilot - subscription-scoped entrypoint.
// Creates the resource group, all AI services, and a cost budget.
targetScope = 'subscription'

@description('Short environment name, e.g. dev')
param env string = 'dev'
@description('Primary region. UAE North for data residency.')
param location string = 'uaenorth'
@description('Object ID of a developer/user to grant data-plane roles (local dev with az login). Empty to skip.')
param developerPrincipalId string = ''
@description('Email for budget alerts')
param budgetEmail string
@description('Monthly budget in USD')
param budgetAmount int = 5
@description('First day of the current month, yyyy-MM-01 (budgets require a month start)')
param budgetStartDate string

@description('Deploy the runtime (Key Vault, monitoring, Container App)')
param deployApp bool = true
@description('Container image. CI replaces this with ghcr.io/<owner>/gov-policy-copilot:<sha>')
param containerImage string = 'mcr.microsoft.com/k8se/quickstart:latest'
@description('Private endpoints + VNet (costs money; off by default)')
param enablePrivateEndpoints bool = false
param entraTenantId string = tenant().tenantId
param entraApiAppId string = ''
param entraSpaClientId string = ''
@description('Object ID of the GitHub Actions OIDC service principal')
param ciPrincipalId string = ''

var prefix = 'govcopilot-${env}'
var tags = { project: 'gov-policy-copilot', env: env, costCenter: 'portfolio' }

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${prefix}'
  location: location
  tags: tags
}

module ai 'modules/ai-services.bicep' = {
  scope: rg
  name: 'ai-services'
  params: {
    prefix: prefix
    location: location
    tags: tags
    developerPrincipalId: developerPrincipalId
  }
}

module monitoring 'modules/monitoring.bicep' = if (deployApp) {
  scope: rg
  name: 'monitoring'
  params: { prefix: prefix, location: location, tags: tags }
}

module app 'modules/app.bicep' = if (deployApp) {
  scope: rg
  name: 'app'
  params: {
    prefix: prefix
    location: location
    tags: tags
    containerImage: containerImage
    openAiName: ai.outputs.openAiName
    searchName: ai.outputs.searchName
    docIntelName: ai.outputs.docIntelName
    contentSafetyName: ai.outputs.contentSafetyName
    languageName: ai.outputs.languageName
    workspaceId: monitoring!.outputs.workspaceId
    appInsightsConnectionString: monitoring!.outputs.appInsightsConnectionString
    ciPrincipalId: ciPrincipalId
    envVars: [
      { name: 'APP_ENV', value: env }
      { name: 'LLM_PROVIDER', value: 'azure_openai' }
      { name: 'AZURE_OPENAI_ENDPOINT', value: ai.outputs.openAiEndpoint }
      { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT', value: ai.outputs.chatDeployment }
      { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: ai.outputs.embeddingDeployment }
      { name: 'AZURE_SEARCH_ENDPOINT', value: ai.outputs.searchEndpoint }
      { name: 'CONTENT_SAFETY_ENDPOINT', value: ai.outputs.contentSafetyEndpoint }
      { name: 'LANGUAGE_ENDPOINT', value: ai.outputs.languageEndpoint }
      { name: 'RERANKER', value: 'none' }
      { name: 'GUARDRAILS_FAIL_CLOSED', value: 'true' }
      { name: 'REVIEW_DB_PATH', value: '/tmp/reviews.db' }
      { name: 'AUTH_ENABLED', value: empty(entraApiAppId) ? 'false' : 'true' }
      { name: 'ENTRA_TENANT_ID', value: entraTenantId }
      { name: 'ENTRA_API_AUDIENCE', value: 'api://${entraApiAppId}' }
      { name: 'ENTRA_SPA_CLIENT_ID', value: entraSpaClientId }
    ]
  }
}

module privateNetworking 'modules/private-endpoints.bicep' = if (deployApp && enablePrivateEndpoints) {
  scope: rg
  name: 'private-endpoints'
  params: {
    prefix: prefix
    location: location
    tags: tags
    cognitiveAccountIds: ai.outputs.cognitiveAccountIds
    keyVaultId: app!.outputs.keyVaultId
  }
}

module budget 'modules/budget.bicep' = {
  name: 'budget'
  params: {
    name: 'budget-${prefix}'
    amount: budgetAmount
    email: budgetEmail
    startDate: budgetStartDate
  }
}

output resourceGroup string = rg.name
output openAiEndpoint string = ai.outputs.openAiEndpoint
output searchEndpoint string = ai.outputs.searchEndpoint
output docIntelEndpoint string = ai.outputs.docIntelEndpoint
output chatDeployment string = ai.outputs.chatDeployment
output embeddingDeployment string = ai.outputs.embeddingDeployment
output contentSafetyEndpoint string = ai.outputs.contentSafetyEndpoint
output languageEndpoint string = ai.outputs.languageEndpoint
output appUrl string = deployApp ? app!.outputs.appUrl : ''
output appName string = deployApp ? app!.outputs.appName : ''
