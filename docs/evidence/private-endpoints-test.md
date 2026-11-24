# Private endpoint test evidence

Deployed 2026-11-24T13:27:20Z from `infra/modules/private-endpoints.bicep` (deployment `pe-test`), torn down the same day. Public network access on the services was left enabled during the test so the live demo kept working; in a locked-down deployment it would be set to `Disabled` and the Container Apps environment VNet-integrated.

## Private endpoints and connection state
```
Name                                  State     Target
------------------------------------  --------  --------
pe-aoai-govcopilot-dev-spemmlgtc6f7m  Approved  account
pe-cs-govcopilot-dev-spemmlgtc6f7m    Approved  account
pe-di-govcopilot-dev-spemmlgtc6f7m    Approved  account
pe-kv-govcopilot-dev                  Approved  vault
pe-lang-govcopilot-dev-spemmlgtc6f7m  Approved  account
```

## Private DNS A records
```
privatelink.cognitiveservices.azure.com	cs-govcopilot-dev-spemmlgtc6f7m	10.40.2.4
privatelink.cognitiveservices.azure.com	di-govcopilot-dev-spemmlgtc6f7m	10.40.2.6
privatelink.cognitiveservices.azure.com	lang-govcopilot-dev-spemmlgtc6f7m	10.40.2.7
privatelink.openai.azure.com	aoai-govcopilot-dev-spemmlgtc6f7m	10.40.2.8
privatelink.vaultcore.azure.net	kv-gc-spemmlgtc6f7m	10.40.2.5
```

## VNet / subnets
```
Subnet     Prefix        Delegation
---------  ------------  --------------------------
snet-apps  10.40.0.0/23  Microsoft.App/environments
snet-pe    10.40.2.0/24
```

## Teardown
Private endpoints, DNS zone links, private DNS zones and the VNet were deleted at 2026-11-24T13:33Z
(~10 minutes of runtime, estimated cost < $0.01). `az resource list` returned no `Microsoft.Network`
resources in the resource group afterwards.

## What this proves / what a production rollout adds
- The Bicep module provisions private endpoints for Azure OpenAI, Document Intelligence, Content
  Safety, Language and Key Vault, with privatelink DNS zones resolving each service to a private IP.
- Production would additionally: set `publicNetworkAccess: Disabled` on each service, move the
  Container Apps environment to a workload-profiles environment in `snet-apps`, and upgrade AI Search
  to Basic+ (Free tier does not support private endpoints).
