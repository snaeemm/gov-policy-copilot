using 'main.bicep'

param env = 'dev'
param location = 'uaenorth'
param budgetEmail = 'snaeemnm@outlook.com'
param budgetAmount = 5
param budgetStartDate = '2026-11-01'
// developerPrincipalId is passed at deploy time: az ad signed-in-user show --query id -o tsv
