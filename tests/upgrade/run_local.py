"""Run a BKFlow command with dedicated loopback services and a scrubbed environment."""

import argparse
import os
from pathlib import Path

LOCAL_SETTINGS = """
import os
from redis import Redis

role = os.environ["BKFLOW_MODULE_TYPE"]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.mysql",
    "NAME": "bkflow_lts_" + role,
    "USER": "root", "PASSWORD": "", "HOST": "127.0.0.1", "PORT": "13306", "CONN_MAX_AGE": 0,
    "TEST": {"NAME": "test_bkflow_lts_" + os.environ["BKFLOW_REHEARSAL_VERSION"] + "_" + role},
}}
REDIS = {"host": "127.0.0.1", "port": 16379, "db": 0}
redis_inst = Redis(**REDIS)
BROKER_URL = "amqp://guest:guest@127.0.0.1:15673//"
CELERY_RESULT_BACKEND = "django-db"
CACHES = {name: {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"} for name in ("default", "login_db")}
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
INTERFACE_APP_URL = "http://127.0.0.1:19999"
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True, dest="interpreter")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", choices=("old", "new"), required=True)
    parser.add_argument("role", choices=("engine", "interface"))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error("A Python script or -m command is required")
    root = args.root.resolve()
    output = args.output.resolve()
    config = output / "config"
    config.mkdir(parents=True, exist_ok=True)
    (output / "logs").mkdir(exist_ok=True)
    temporary_config = config / f"local_settings.{os.getpid()}.tmp"
    temporary_config.write_text(LOCAL_SETTINGS)
    temporary_config.replace(config / "local_settings.py")
    # A project-local override would take precedence over our isolated configuration.
    if any((root / name).exists() for name in ("local_settings.py", "local_settings")):
        parser.error("Use a clean checkout without project-local local_settings")
    env = {
        "HOME": str(Path.home()),
        "PATH": os.defpath,
        "LANG": "en_US.UTF-8",
        "TMPDIR": "/tmp",
    }
    for line in (root / "tests" / (args.role + ".env")).read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    env.update(
        {
            "PYTHONPATH": str(root) + os.pathsep + str(config),
            "BKFLOW_MODULE_CODE": "lts",
            "BK_ENV": "development",
            "BKPAAS_LOG_PATH": str(output / "logs"),
            "BKFLOW_CELERY_BROKER_URL": "amqp://guest:guest@127.0.0.1:15673//",
            "BK_APIGW_NETLOC_PATTERN": r"^localhost/(?P<api_name>[\\w-]+)",
            "REDIS_HOST": "127.0.0.1",
            "REDIS_PORT": "16379",
            "REDIS_DB": "0",
            "BK_API_URL_TMPL": "http://127.0.0.1:19999/{api_name}",
            "BKPAAS_LOGIN_URL": "http://127.0.0.1:19999/login/",
            "BKPAAS_APIGW_OAUTH_API_URL": "http://127.0.0.1:19999/oauth",
            "BK_COMPONENT_API_URL": "http://127.0.0.1:19999/",
            "BKFLOW_REHEARSAL_VERSION": args.version,
            "PRIVATE_SECRET": "test_secret_key_32_bytes_long!",
            "ENABLE_BK_PLUGIN_AUTHORIZATION": "1",
        }
    )
    if "pytest" in args.command:
        env.pop("BKFLOW_MODULE_CODE")
        env.pop("BKFLOW_CELERY_BROKER_URL")
    # Keep the virtualenv executable path: resolving its symlink would bypass the virtualenv.
    interpreter = str(args.interpreter.absolute())
    os.chdir(root)
    os.execve(interpreter, [interpreter, *args.command], env)


if __name__ == "__main__":
    main()
