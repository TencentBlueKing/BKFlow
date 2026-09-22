# Packaging and deployment compatibility

This guide covers the seven confirmed source/documentation gaps addressed in 1.11.14: application identity, platform APIs, timezones, credential encryption, administrator initialization, bilingual documentation, and release versioning. It does not certify the 37-item release checklist without target-environment and artifact evidence.

## Application identity and existing services

Standard Smart packages use `bk_flow`. Runtime authentication continues to use the identity and secret injected by PaaS (`BKPAAS_APP_ID` / `BKPAAS_APP_SECRET`). Upgrade an existing cloud deployment in its original PaaS application, preserving its databases, keys, gateway, and module records.

For a Smart upgrade of an existing application, render a matching descriptor **before packaging**:

```bash
BKFLOW_PACKAGE_APP_CODE=bk_flow_engine \
BKFLOW_PACKAGE_APIGW_NAME=legacy-bkflow-gateway \
python scripts/render_app_desc.py --output /tmp/bkflow-package/app_desc.yaml
```

Replace example values with the actual registered identifiers. Put the result at the Smart package root and copy source to `src/` using the existing pipeline. The renderer updates references to the application's own modules and retains external service references. It only generates the descriptor; it does not build, upload, or deploy a package. Source-based deployments do not need these packaging variables.

`BK_APIGW_NAME`, when nonempty, overrides the gateway name derived from the actual APP_Code. Underscores are converted to hyphens as before. Without an override, `bk_flow` uses `bk-flow`, and `bk_flow_engine` uses `bk-flow-engine`.

| Runtime setting | Purpose |
| --- | --- |
| `BKAPP_APIGW_API_HOST` | Interface gateway backend URL; overrides discovery of the default module |
| `BKAPP_INNER_CALLBACK_ENTRY` | Callback base URL; set in modules generating callbacks, usually Engine |
| `BKAPP_DEFAULT_ENGINE_MODULE_ENTRY` | Default Engine URL used by Interface initialization |
| `INTERFACE_APP_URL` | Interface URL used by each Engine; overrides service discovery |
| `INTERFACE_APP_INTERNAL_TOKEN` | Each Engine's token for calling Interface |
| `DEFAULT_ENGINE_APP_INTERNAL_TOKEN` | Token used to initialize the default Engine record |
| `APP_INTERNAL_TOKEN` | Token accepted by the current module |

Retain URL subpaths and existing tokens. The default-module initialization creates missing records; it does not overwrite existing `ModuleInfo` URLs or tokens. An address override therefore does not migrate an existing record. Verify existing routing before deployment.

## Modern and legacy platform APIs

Set the same `BKFLOW_PLATFORM_API_MODE` in Interface and every Engine:

- `apigw` (default): modern user-management, CMSI, and ITSM4 APIs for both single-tenant (`default`) and multi-tenant deployments.
- `legacy`: old ESB language preferences, member selection, notifications, and approval creation for existing single-tenant platforms.
- Multi-tenant mode always uses APIGW, even if `legacy` is configured.

Modern endpoints use `BK_API_URL_TMPL` and `BK_APIGW_STAGE_NAME` for `bk-user-web`, `bk-login`, `bk-cmsi`, and `bk-itsm4`. Configure actual addresses and gateway permissions. Language preferences use `PUT /api/v3/open-web/tenant/current-user/language/` with the user's login credentials and `X-Bk-Tenant-Id`.

Before using modern single-tenant approvals, run the following in Interface after granting the required ITSM4 permissions:

```bash
python manage.py init_tenant --tenant_id default
```

Use the actual tenant ID for multi-tenant initialization. This command writes to remote ITSM4; validate successful initialization, repeat execution, and failure recovery in the target environment. Legacy platforms keep their original initialization process.

Existing approval outputs select the old `sn` or new `id` protocol. If old tickets remain after switching to APIGW mode, explicitly retain `BK_ITSM_API_ENTRY` pointing to the compatible old ITSM service. Modern mode never silently constructs an ESB fallback URL. Existing workflow keys remain unchanged.

Minimal compatibility settings for an older single-tenant cloud platform:

```bash
BKFLOW_PLATFORM_API_MODE=legacy
BKFLOW_CREDENTIAL_CIPHER=AES
```

Preserve the original tenant switch, platform identity, ESB/ITSM endpoints, `PRIVATE_SECRET`, and module tokens.

## Timezones

Valid IANA timezone preferences take precedence in this order: internal `Bkflow-Internal-Time-Zone` header, standard `blueking-timezone` header, `blueking_timezone` cookie, matching session value, modern platform user preference, deployment `TIME_ZONE`. Invalid values are ignored. Both tenant modes follow this rule. Legacy mode with no explicit preference retains the deployment default. New periodic triggers save the effective user timezone in `config.timezone` and pass it to Engine. Updates that omit this field preserve the existing schedule timezone. Older schedules without the field keep their saved Engine crontab timezone. The UI displays and previews the timezone of new schedules.

## Credential encryption and rollback

`BKFLOW_CREDENTIAL_CIPHER` selects writes: `AES` (default) or `SM4`. Existing AES format remains unchanged. SM4 uses BlueKing Python SDK 2.0.1 with SM4-GCM, a version prefix, random nonce, and authenticated ciphertext. Updated code reads both formats regardless of the selected write mode. Historical migrations retain the original `BaseCrypt` implementation.

1. Retain `PRIVATE_SECRET` and deploy all credential readers/writers with AES selected. Verify existing credentials.
2. Only after every module supports the new format, select SM4 for new and updated credentials.
3. Existing AES records are not rewritten automatically. If all stored credentials must use SM4, back up and resave them in the target environment, then verify the stored format.
4. Switching back to AES affects future writes only; new code can still read SM4. Once SM4 data exists, do not roll back to older code until that data has been converted back using the new code and verified, or restore a matching backup. Key rotation requires a separate migration.

This change covers business `Credential.content` storage; it does not by itself certify every dependency or deployment for commercial cryptography compliance.

## Administrator initialization

In multi-tenant mode, the user must first log in so that their actual tenant identity exists locally. Only users of the `system` tenant can be granted Django superuser status:

```bash
python manage.py sync_superuser --usernames <system-username>
```

`BKFLOW_INIT_SUPERUSERS` remains supported by the release step. If any listed user is unknown or belongs to another tenant, the whole batch is rejected and that release step fails. Leave it unset during initial deployment until users have logged in, then authorize manually. Existing superuser grants are not automatically revoked; audit historical grants before enabling multi-tenancy. Single-tenant initialization retains its existing create/update behavior.

BKFlow business administration maps to **space administrators**:

```bash
python manage.py grant_space_admin --username <username> --tenant-id <tenant> --space-id <space-id>
```

The active user and space must exist. In multi-tenant mode, both must belong to the specified tenant; single-tenant mode accepts only `default`. This command adds the user idempotently to the space's `superusers` configuration without granting Django superuser/staff flags or access to other spaces. Native Django admin remains disabled in multi-tenant mode.

## Versioning and bilingual documentation

Source version 1.11.14 includes changes from tag `V1.11.13` to master plus this remediation. Create a new immutable tag after merging, and record the exact source SHA and artifact/image digests. Do not move `V1.11.13`. A merged PR or local test is not proof of publication.

English API documentation has the same 94 filenames and example payloads as Chinese documentation. Run `scripts/apigw_docs.sh` to rebuild the archive with both `zh/` and `en/`. Business example values remain unchanged for structural comparison.

Help links prefer `BKFLOW_DOC_URL_ZH` / `BKFLOW_DOC_URL_EN`. Otherwise, an explicitly configured `BKFLOW_DOC_VERSION` selects a published documentation-center version under `BK_DOC_CENTER_HOST`. Without these settings, links use the current repository guide / English README rather than the old 1.8 documentation. Private deployments should configure internally reachable documentation URLs.

## Deployment validation

Run the migrations belonging to Interface, every Engine, and the statistics database separately. Verify/backfill historical tenant ownership before enabling multi-tenancy. Do not read Interface-owned data through Engine ORM access.

Validate application/gateway identity, module routing, ongoing callbacks, notifications, approvals, single- and multi-tenant authorization, non-Shanghai timezone display/API/scheduling, login renewal/logout, subpaths, IPv6, missing-dependency guidance, and health probes on the actual target platform. Release approval also requires the corresponding Smart package/image, pipeline records, security scans, BKOP stability evidence, and delivery sign-off.
