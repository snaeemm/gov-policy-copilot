// AI services: Azure OpenAI, AI Search (free), Document Intelligence (F0).
// Keyless by design: local auth disabled on Cognitive Services; access via Entra ID RBAC.

param prefix string
param location string
param tags object
param developerPrincipalId string
@description('Capacity in thousands of tokens per minute')
param chatCapacity int = 10
param embeddingCapacity int = 10

var suffix = uniqueString(resourceGroup().id)

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'aoai-${prefix}-${suffix}'
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: 'aoai-${prefix}-${suffix}'
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource chat 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: 'gpt-5-mini'
  // GlobalStandard is the only SKU offered in UAE North for this model - see ADR on data residency.
  sku: { name: 'GlobalStandard', capacity: chatCapacity }
  properties: {
    model: { format: 'OpenAI', name: 'gpt-5-mini', version: '2025-08-07' }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource embedding 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: 'text-embedding-3-small'
  dependsOn: [ chat ] // deployments on one account must be serialized
  // Regional Standard keeps embedding inference in UAE North.
  sku: { name: 'Standard', capacity: embeddingCapacity }
  properties: {
    model: { format: 'OpenAI', name: 'text-embedding-3-small', version: '1' }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource docIntel 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'di-${prefix}-${suffix}'
  location: location
  tags: tags
  kind: 'FormRecognizer'
  sku: { name: 'F0' }
  properties: {
    customSubDomainName: 'di-${prefix}-${suffix}'
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource contentSafety 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'cs-${prefix}-${suffix}'
  location: location
  tags: tags
  kind: 'ContentSafety'
  sku: { name: 'F0' }
  properties: {
    customSubDomainName: 'cs-${prefix}-${suffix}'
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource language 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'lang-${prefix}-${suffix}'
  location: location
  tags: tags
  kind: 'TextAnalytics'
  sku: { name: 'F0' }
  properties: {
    customSubDomainName: 'lang-${prefix}-${suffix}'
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: 'srch-${prefix}-${suffix}'
  location: location
  tags: tags
  sku: { name: 'free' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    publicNetworkAccess: 'enabled'
    authOptions: { aadOrApiKey: { aadAuthFailureMode: 'http401WithBearerChallenge' } }
  }
}

// Built-in role definition IDs
var roles = {
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'        // Cognitive Services OpenAI User
  cogServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'   // Cognitive Services User
  searchIndexContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7' // Search Index Data Contributor
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0' // Search Service Contributor
}

resource devOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(developerPrincipalId)) {
  name: guid(openAi.id, developerPrincipalId, roles.openAiUser)
  scope: openAi
  properties: { principalId: developerPrincipalId, principalType: 'User', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser) }
}
resource devDocIntel 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(developerPrincipalId)) {
  name: guid(docIntel.id, developerPrincipalId, roles.cogServicesUser)
  scope: docIntel
  properties: { principalId: developerPrincipalId, principalType: 'User', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cogServicesUser) }
}
resource devContentSafety 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(developerPrincipalId)) {
  name: guid(contentSafety.id, developerPrincipalId, roles.cogServicesUser)
  scope: contentSafety
  properties: { principalId: developerPrincipalId, principalType: 'User', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cogServicesUser) }
}
resource devLanguage 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(developerPrincipalId)) {
  name: guid(language.id, developerPrincipalId, roles.cogServicesUser)
  scope: language
  properties: { principalId: developerPrincipalId, principalType: 'User', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cogServicesUser) }
}
resource devSearchData 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(developerPrincipalId)) {
  name: guid(search.id, developerPrincipalId, roles.searchIndexContributor)
  scope: search
  properties: { principalId: developerPrincipalId, principalType: 'User', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexContributor) }
}
resource devSearchSvc 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(developerPrincipalId)) {
  name: guid(search.id, developerPrincipalId, roles.searchServiceContributor)
  scope: search
  properties: { principalId: developerPrincipalId, principalType: 'User', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchServiceContributor) }
}

output openAiEndpoint string = openAi.properties.endpoint
output docIntelEndpoint string = docIntel.properties.endpoint
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output chatDeployment string = chat.name
output embeddingDeployment string = embedding.name
output contentSafetyEndpoint string = contentSafety.properties.endpoint
output languageEndpoint string = language.properties.endpoint
output openAiName string = openAi.name
output searchName string = search.name
output docIntelName string = docIntel.name
output contentSafetyName string = contentSafety.name
output languageName string = language.name
