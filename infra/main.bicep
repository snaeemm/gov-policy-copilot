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
