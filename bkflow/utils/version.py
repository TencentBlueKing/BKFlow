import semver


def bump_custom(version: str):
    """
    计算自定义版本号
    1.0.0 -> 1.0.1
    """
    parsed_version = semver.VersionInfo.parse(version)

    if parsed_version.patch == 9:
        new_minor = parsed_version.minor + 1
        if new_minor > 9:
            new_version = semver.VersionInfo(major=parsed_version.major + 1, minor=0, patch=0)
        else:
            new_version = semver.VersionInfo(major=parsed_version.major, minor=new_minor, patch=0)
    else:
        new_version = parsed_version.bump_patch()

    return str(new_version)
