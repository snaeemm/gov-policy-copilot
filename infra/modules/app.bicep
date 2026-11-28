// Runtime: user-assigned managed identity, Key Vault, Container Apps environment + app.
// The identity gets least-privilege data-plane roles on each AI service (no API keys anywhere).
param prefix string
param location string
param tags object
param containerImage string
param openAiName string
param searchName string
#disable-next-line no-unused-params
param docIntelName string
param contentSafetyName string
param languageName string
param workspaceId string
@secure()
param appInsightsConnectionString string
param envVars array
@description('Optional: principal (e.g. GitHub OIDC service principal) granted Contributor on this RG and data-plane read roles for the CI eval gate')
param ciPrincipalId string = ''

var suffix = uniqueString(resourceGroup().id)

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${prefix}'
  location: location
  tags: tags
}

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-gc-${suffix}'
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

resource aiSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'appinsights-connection-string'
  properties: { value: appInsightsConnectionString }
}

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = { name: openAiName }
resource contentSafety 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = { name: contentSafetyName }
resource language 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = { name: languageName }
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' existing = { name: searchName }

var roleIds = {
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  cogServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  searchIndexReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  kvSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  contributor: 'b24988ac-6180-42a0-ab88-20f7382dd24c'
}
func roleDef(id string) string => subscriptionResourceId('Microsoft.Authorization/roleDefinitions', id)

// --- runtime identity roles ---
resource rOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAi.id, uami.id, roleIds.openAiUser)
  scope: openAi
  properties: { principalId: uami.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: roleDef(roleIds.openAiUser) }
}
resource rCs 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(contentSafety.id, uami.id, roleIds.cogServicesUser)
  scope: contentSafety
  properties: { principalId: uami.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: roleDef(roleIds.cogServicesUser) }
}
resource rLang 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(language.id, uami.id, roleIds.cogServicesUser)
  scope: language
  properties: { principalId: uami.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: roleDef(roleIds.cogServicesUser) }
}
resource rSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, uami.id, roleIds.searchIndexReader)
  scope: search
  properties: { principalId: uami.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: roleDef(roleIds.searchIndexReader) }
}
resource rKv 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, uami.id, roleIds.kvSecretsUser)
  scope: kv
  properties: { principalId: uami.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: roleDef(roleIds.kvSecretsUser) }
}

// --- CI (GitHub OIDC) roles: deploy app revisions + run the eval gate ---
resource ciContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(ciPrincipalId)) {
  name: guid(resourceGroup().id, ciPrincipalId, roleIds.contributor)
  properties: { principalId: ciPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleDef(roleIds.contributor) }
}
resource ciOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(ciPrincipalId)) {
  name: guid(openAi.id, ciPrincipalId, roleIds.openAiUser)
  scope: openAi
  properties: { principalId: ciPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleDef(roleIds.openAiUser) }
}
resource ciCs 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(ciPrincipalId)) {
  name: guid(contentSafety.id, ciPrincipalId, roleIds.cogServicesUser)
  scope: contentSafety
  properties: { principalId: ciPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleDef(roleIds.cogServicesUser) }
}
resource ciLang 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(ciPrincipalId)) {
  name: guid(language.id, ciPrincipalId, roleIds.cogServicesUser)
  scope: language
  properties: { principalId: ciPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleDef(roleIds.cogServicesUser) }
}
resource ciSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(ciPrincipalId)) {
  name: guid(search.id, ciPrincipalId, roleIds.searchIndexReader)
  scope: search
  properties: { principalId: ciPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleDef(roleIds.searchIndexReader) }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${prefix}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(workspaceId, '2023-09-01').customerId
        sharedKey: listKeys(workspaceId, '2023-09-01').primarySharedKey
      }
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${prefix}'
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${uami.id}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      activeRevisionsMode: 'Multiple' // enables blue/green + instant rollback via traffic split
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
        traffic: [ { latestRevision: true, weight: 100 } ]
      }
      secrets: [
        {
          name: 'appinsights-cs'
          keyVaultUrl: aiSecret.properties.secretUri
          identity: uami.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: containerImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: concat(envVars, [
            { name: 'AZURE_CLIENT_ID', value: uami.properties.clientId }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-cs' }
          ])
          probes: [
            { type: 'Liveness', httpGet: { path: '/healthz', port: 8000 }, periodSeconds: 30 }
            { type: 'Readiness', httpGet: { path: '/healthz', port: 8000 }, periodSeconds: 10 }
          ]
        }
      ]
      scale: {
        minReplicas: 0 // scale to zero = $0 when idle (cold start ~10-20s)
        maxReplicas: 2
        rules: [ { name: 'http', http: { metadata: { concurrentRequests: '20' } } } ]
      }
    }
  }
  dependsOn: [ rKv, rOpenAi, rSearch, rCs, rLang ]
}

output appUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output appName string = app.name
output identityClientId string = uami.properties.clientId
output keyVaultName string = kv.name
output keyVaultId string = kv.id
output identityPrincipalId string = uami.properties.principalId
