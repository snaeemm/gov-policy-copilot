#!/usr/bin/env bash
# Idempotent Microsoft Entra ID setup (Graph objects can't be created by ARM/Bicep without the
# preview Graph extension). Creates:
#   1. API app registration with App Roles (Copilot.Viewer / Reviewer / Admin) + scope access_as_user
#   2. SPA app registration (MSAL.js, auth code + PKCE) pre-authorized on the API
#   3. GitHub Actions app registration with OIDC federated credentials (no client secret)
# and assigns the signed-in user the Copilot.Admin role.
# Usage: infra/scripts/setup-entra.sh <app-url> <github-owner/repo>
set -euo pipefail
APP_URL="${1:?app url}"; REPO="${2:?owner/repo}"
API_NAME="gov-policy-copilot-api"; SPA_NAME="gov-policy-copilot-web"; GH_NAME="gov-policy-copilot-github"
uuid() { python3 -c 'import uuid;print(uuid.uuid4())'; }
appid_of() { az ad app list --display-name "$1" --query "[0].appId" -o tsv; }

# ---------- API ----------
API_ID=$(appid_of "$API_NAME")
if [[ -z "$API_ID" ]]; then
  ROLES=$(cat <<JSON
[{"allowedMemberTypes":["User"],"description":"Ask questions","displayName":"Viewer","id":"$(uuid)","isEnabled":true,"value":"Copilot.Viewer"},
 {"allowedMemberTypes":["User"],"description":"Review escalated answers","displayName":"Reviewer","id":"$(uuid)","isEnabled":true,"value":"Copilot.Reviewer"},
 {"allowedMemberTypes":["User"],"description":"Administer the copilot","displayName":"Admin","id":"$(uuid)","isEnabled":true,"value":"Copilot.Admin"}]
JSON
)
  API_ID=$(az ad app create --display-name "$API_NAME" --sign-in-audience AzureADMyOrg --app-roles "$ROLES" --query appId -o tsv)
  OBJ=$(az ad app show --id "$API_ID" --query id -o tsv)
  SCOPE_ID=$(uuid)
  az rest --method PATCH --url "https://graph.microsoft.com/v1.0/applications/$OBJ" --headers Content-Type=application/json --body "{
    \"identifierUris\": [\"api://$API_ID\"],
    \"api\": {\"requestedAccessTokenVersion\": 2, \"oauth2PermissionScopes\": [{\"id\": \"$SCOPE_ID\", \"adminConsentDescription\": \"Access Gov Policy Copilot\", \"adminConsentDisplayName\": \"Access Gov Policy Copilot\", \"userConsentDescription\": \"Access Gov Policy Copilot\", \"userConsentDisplayName\": \"Access Gov Policy Copilot\", \"isEnabled\": true, \"type\": \"User\", \"value\": \"access_as_user\"}]}
  }"
  az ad sp create --id "$API_ID" >/dev/null
  SP_OBJ=$(az ad sp show --id "$API_ID" --query id -o tsv)
  # Require an app role assignment to obtain a token (deny-by-default).
  az rest --method PATCH --url "https://graph.microsoft.com/v1.0/servicePrincipals/$SP_OBJ" --headers Content-Type=application/json --body '{"appRoleAssignmentRequired": true}'
fi
API_OBJ=$(az ad app show --id "$API_ID" --query id -o tsv)
SCOPE_ID=$(az ad app show --id "$API_ID" --query "api.oauth2PermissionScopes[0].id" -o tsv)
API_SP=$(az ad sp show --id "$API_ID" --query id -o tsv)

# ---------- SPA ----------
SPA_ID=$(appid_of "$SPA_NAME")
if [[ -z "$SPA_ID" ]]; then
  SPA_ID=$(az ad app create --display-name "$SPA_NAME" --sign-in-audience AzureADMyOrg --query appId -o tsv)
  az ad sp create --id "$SPA_ID" >/dev/null
fi
SPA_OBJ=$(az ad app show --id "$SPA_ID" --query id -o tsv)
az rest --method PATCH --url "https://graph.microsoft.com/v1.0/applications/$SPA_OBJ" --headers Content-Type=application/json --body "{
  \"spa\": {\"redirectUris\": [\"$APP_URL\", \"$APP_URL/\", \"http://127.0.0.1:8410\", \"http://127.0.0.1:8410/\"]},
  \"requiredResourceAccess\": [{\"resourceAppId\": \"$API_ID\", \"resourceAccess\": [{\"id\": \"$SCOPE_ID\", \"type\": \"Scope\"}]}]
}"
az rest --method PATCH --url "https://graph.microsoft.com/v1.0/applications/$API_OBJ" --headers Content-Type=application/json --body "{
  \"api\": {\"preAuthorizedApplications\": [{\"appId\": \"$SPA_ID\", \"delegatedPermissionIds\": [\"$SCOPE_ID\"]}]}
}"

# ---------- assign signed-in user Copilot.Admin ----------
ME=$(az ad signed-in-user show --query id -o tsv)
ADMIN_ROLE=$(az ad app show --id "$API_ID" --query "appRoles[?value=='Copilot.Admin'].id | [0]" -o tsv)
EXISTS=$(az rest --method GET --url "https://graph.microsoft.com/v1.0/servicePrincipals/$API_SP/appRoleAssignedTo" --query "value[?principalId=='$ME' && appRoleId=='$ADMIN_ROLE'] | length(@)" -o tsv)
if [[ "$EXISTS" == "0" ]]; then
  az rest --method POST --url "https://graph.microsoft.com/v1.0/servicePrincipals/$API_SP/appRoleAssignedTo" --headers Content-Type=application/json \
    --body "{\"principalId\": \"$ME\", \"resourceId\": \"$API_SP\", \"appRoleId\": \"$ADMIN_ROLE\"}" >/dev/null
fi

# ---------- GitHub OIDC ----------
GH_ID=$(appid_of "$GH_NAME")
if [[ -z "$GH_ID" ]]; then
  GH_ID=$(az ad app create --display-name "$GH_NAME" --sign-in-audience AzureADMyOrg --query appId -o tsv)
  az ad sp create --id "$GH_ID" >/dev/null
fi
for SUBJ in "ref:refs/heads/main" "environment:production"; do
  NAME="gh-$(echo "$SUBJ" | tr ':/' '--')"
  if [[ -z $(az ad app federated-credential list --id "$GH_ID" --query "[?name=='$NAME'].name" -o tsv) ]]; then
    az ad app federated-credential create --id "$GH_ID" --parameters "{\"name\": \"$NAME\", \"issuer\": \"https://token.actions.githubusercontent.com\", \"subject\": \"repo:$REPO:$SUBJ\", \"audiences\": [\"api://AzureADTokenExchange\"]}" >/dev/null
  fi
done
GH_SP=$(az ad sp show --id "$GH_ID" --query id -o tsv)

cat <<OUT
API_APP_ID=$API_ID
SPA_APP_ID=$SPA_ID
GITHUB_APP_ID=$GH_ID
GITHUB_SP_OBJECT_ID=$GH_SP
TENANT_ID=$(az account show --query tenantId -o tsv)
OUT
