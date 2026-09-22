![BKFlow](./docs/pics/logo_zh.png)

[![License](https://img.shields.io/badge/license-MIT-brightgreen.svg)](./LICENSE)
[![Release](https://img.shields.io/github/v/release/TencentBlueKing/BKFlow)](https://github.com/TencentBlueKing/BKFlow/releases)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/TencentBlueKing/BKFlow/pulls)

English | [简体中文](./README.md)

# BlueKing Flow Engine Service

BKFlow is a Python workflow platform for systems that need visual workflow design, task execution, and rule-based decisions.

## Features

- Embed the workflow canvas in your application and control access with resource tokens.
- Create, execute, pause, resume, and revoke workflow tasks through APIs.
- Extend workflows with built-in plugins, remote plugins, and Uniform API plugins.
- Debug workflows globally or one node at a time, including mocks and conditional gateways.
- Manage decision tables, workflow versions, space settings, credentials, and webhook subscriptions.
- Isolate spaces, templates, tasks, and plugin catalogs by tenant when multi-tenancy is enabled; retain single-tenant compatibility.

## Architecture and integration

The **Interface** module handles user access, authorization, spaces, templates, and plugin configuration. **Engine** modules execute tasks. They use separate databases and authenticated internal APIs; deploy and migrate each module separately.

An integrating application creates a space and templates through the gateway. It requests resource tokens for authenticated users before embedding the canvas or task pages. Application authentication and tenant headers do not replace user or resource authorization. See the [English API reference](./bkflow/apigw/docs/en) for endpoint parameters, permissions, and examples.

## Deployment and upgrade

The standard Smart application identifier is `bk_flow`. Existing cloud applications can retain their registered identity, gateway, service addresses, and credentials using packaging and runtime environment settings.

- [Deployment and compatibility guide](./docs/guide/release_compatibility_en.md)
- [Current release notes](./version_logs_md_en/V1.11.14_2026-09-17.md)
- [Release history](./version_logs_md_en)
- [Chinese product and integration guides](./docs/guide)

New platforms use APIGW for language preferences, member selection, notifications, and approvals. Older single-tenant platforms can explicitly select `BKFLOW_PLATFORM_API_MODE=legacy`. Credential storage supports SM4-GCM while continuing to read existing AES data. Review the deployment guide before changing either setting.

## Development

Python dependencies are in `requirements.txt`; frontend dependencies and scripts are in `frontend/package.json`. Test entry points are `scripts/run_interface_unit_test.sh`, `scripts/run_engine_unit_test.sh`, and the frontend `test:plugin-form` script. Configure isolated test databases and caches before running backend tests. The internal-only `django-bkvision` dependency requires the internal package index; public CI explicitly omits it.

## Support and contributing

- [Source and issues](https://github.com/TencentBlueKing/BKFlow)
- [BlueKing community](https://bk.tencent.com/s-mart/community)
- [BlueKing documentation](https://bk.tencent.com/docs/)
- [Contributing](https://github.com/TencentBlueKing/BKFlow/pulls)

Related projects: [BK-SOPS](https://github.com/TencentBlueKing/bk-sops), [BK-CMDB](https://github.com/Tencent/bk-cmdb), [BK-CI](https://github.com/Tencent/bk-ci), [BK-BCS](https://github.com/Tencent/bk-bcs), [BK-PaaS](https://github.com/Tencent/bk-paas), and [BK-JOB](https://github.com/Tencent/bk-job).

## License

BKFlow is released under the [MIT License](./LICENSE).
