"""为 Smart 包生成环境专用的应用描述，保留源码中的标准产品标识。"""

import argparse
import os
import re
from pathlib import Path

import yaml

DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "app_desc.yaml"


def render_app_desc(source, app_code=None, apigw_name=None):
    """替换应用身份与自身服务发现引用，可独立保留存量网关名称。"""
    description = yaml.safe_load(source)
    original_code = description["app"]["bk_app_code"]
    target_code = app_code or original_code
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", target_code):
        raise ValueError("BKFLOW_PACKAGE_APP_CODE 必须以小写字母开头，仅包含小写字母、数字、下划线或中划线")
    if apigw_name and not re.fullmatch(r"[a-z][a-z0-9_-]*", apigw_name):
        raise ValueError("BKFLOW_PACKAGE_APIGW_NAME 必须以小写字母开头，仅包含小写字母、数字、下划线或中划线")

    description["app"]["bk_app_code"] = target_code
    for module in description["modules"].values():
        services = module.get("svc_discovery", {}).get("bk_saas", [])
        for index, service in enumerate(services):
            if isinstance(service, dict) and service.get("bk_app_code") == original_code:
                service["bk_app_code"] = target_code
            elif service == original_code:
                services[index] = {"bk_app_code": target_code}

    if apigw_name:
        variables = description["modules"]["default"].setdefault("env_variables", [])
        variables[:] = [item for item in variables if item["key"] != "BK_APIGW_NAME"]
        variables.append({"key": "BK_APIGW_NAME", "value": apigw_name, "description": "保留目标环境的 APIGW 名称"})

    return yaml.safe_dump(description, allow_unicode=True, sort_keys=False)


def main():
    """将部署环境覆盖值写到包目录，不覆盖仓库中的源描述。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="源应用描述，默认为仓库 app_desc.yaml")
    parser.add_argument("--output", type=Path, required=True, help="打包暂存目录中的 app_desc.yaml 路径")
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error("输出路径不能覆盖源应用描述，请使用打包暂存目录")
    try:
        rendered = render_app_desc(
            args.source.read_text(encoding="utf-8"),
            app_code=os.getenv("BKFLOW_PACKAGE_APP_CODE"),
            apigw_name=os.getenv("BKFLOW_PACKAGE_APIGW_NAME"),
        )
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
