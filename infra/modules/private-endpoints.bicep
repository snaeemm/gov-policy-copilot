// Private networking (OFF by default - costs ~$7/endpoint/month).
// Creates a VNet, private endpoints + private DNS zones for Azure OpenAI, Key Vault and the
// other Cognitive Services accounts, and disables their public network access when enabled.
// Note: AI Search private endpoints require Basic tier or higher (Free tier is excluded), and
// the Container Apps environment must be VNet-integrated (workload profiles) to reach them.
param prefix string
param location string
param tags object
param cognitiveAccountIds array
param keyVaultId string

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: 'vnet-${prefix}'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: [ '10.40.0.0/16' ] }
    subnets: [
      { name: 'snet-apps', properties: { addressPrefix: '10.40.0.0/23', delegations: [ { name: 'aca', properties: { serviceName: 'Microsoft.App/environments' } } ] } }
      { name: 'snet-pe', properties: { addressPrefix: '10.40.2.0/24', privateEndpointNetworkPolicies: 'Disabled' } }
    ]
  }
}

var zones = [ 'privatelink.cognitiveservices.azure.com', 'privatelink.openai.azure.com', 'privatelink.vaultcore.azure.net' ]

resource dns 'Microsoft.Network/privateDnsZones@2020-06-01' = [for z in zones: {
  name: z
  location: 'global'
  tags: tags
}]

resource links 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [for (z, i) in zones: {
  parent: dns[i]
  name: 'link-${prefix}'
  location: 'global'
  properties: { virtualNetwork: { id: vnet.id }, registrationEnabled: false }
}]

resource cogPe 'Microsoft.Network/privateEndpoints@2024-01-01' = [for (id, i) in cognitiveAccountIds: {
  name: 'pe-${last(split(id, '/'))}'
  location: location
  tags: tags
  properties: {
    subnet: { id: vnet.properties.subnets[1].id }
    privateLinkServiceConnections: [ { name: 'cog', properties: { privateLinkServiceId: id, groupIds: [ 'account' ] } } ]
  }
}]

resource cogDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = [for (id, i) in cognitiveAccountIds: {
  parent: cogPe[i]
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      { name: 'cog', properties: { privateDnsZoneId: dns[0].id } }
      { name: 'openai', properties: { privateDnsZoneId: dns[1].id } }
    ]
  }
}]

resource kvPe 'Microsoft.Network/privateEndpoints@2024-01-01' = {
  name: 'pe-kv-${prefix}'
  location: location
  tags: tags
  properties: {
    subnet: { id: vnet.properties.subnets[1].id }
    privateLinkServiceConnections: [ { name: 'kv', properties: { privateLinkServiceId: keyVaultId, groupIds: [ 'vault' ] } } ]
  }
}

resource kvDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = {
  parent: kvPe
  name: 'default'
  properties: { privateDnsZoneConfigs: [ { name: 'kv', properties: { privateDnsZoneId: dns[2].id } } ] }
}

output vnetId string = vnet.id
output appsSubnetId string = vnet.properties.subnets[0].id
