using 'main.bicep'

param env = 'dev'
param location = 'uaenorth'
param budgetEmail = 'snaeemnm@outlook.com'
param budgetAmount = 5
param budgetStartDate = '2026-11-01'
param entraApiAppId = '64947f95-20da-4e3d-a182-a6297bc02c1b'
param entraSpaClientId = '395bacd3-bdd5-449f-aae8-3a6209b8b21a'
param ciPrincipalId = '3fc3f6f4-521b-4252-9155-2f0b0ebe0c6e'
param enablePrivateEndpoints = false
// developerPrincipalId is passed at deploy time: az ad signed-in-user show --query id -o tsv
