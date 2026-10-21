"""
KMS 集成测试脚本

测试按照蓝鲸 PaaS 平台规范的 KMS 集成
"""

import os
import sys


def test_kms_module_import():
    """测试 KMS 模块导入"""
    print("=" * 60)
    print("测试 1: KMS 模块导入")
    print("-" * 60)

    try:
        from bkflow.contrib.kms import decrypt_kms_secrets, is_kms_enabled
        print("✓ bkflow.contrib.kms 模块导入成功")
        print("  - decrypt_kms_secrets()")
        print("  - is_kms_enabled()")
        return True
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return False


def test_bk_kms_sdk():
    """测试 bk-kms-sdk 是否可用"""
    print("\n" + "=" * 60)
    print("测试 2: bk-kms-sdk 可用性")
    print("-" * 60)

    try:
        import bk_kms
        print(f"✓ bk_kms SDK 导入成功")
        print(f"  版本: {bk_kms.__version__}")

        # 测试 decrypt 函数
        if hasattr(bk_kms, 'decrypt'):
            print("✓ decrypt 函数存在")
        else:
            print("✗ decrypt 函数不存在")
            return False

        return True
    except ImportError as e:
        print(f"✗ bk_kms 导入失败: {e}")
        print("  请运行: pip install 'bk-kms-sdk[gm]'")
        return False


def test_kms_disabled():
    """测试 KMS 未启用时的行为"""
    print("\n" + "=" * 60)
    print("测试 3: KMS 未启用时的行为")
    print("-" * 60)

    try:
        from bkflow.contrib.kms import decrypt_kms_secrets, is_kms_enabled

        # 确保 KMS 未启用
        if 'BKPAAS_KMS_ENABLED' in os.environ:
            del os.environ['BKPAAS_KMS_ENABLED']

        # 检查状态
        enabled = is_kms_enabled()
        print(f"  is_kms_enabled() = {enabled}")

        if enabled:
            print("✗ KMS 应该是未启用状态")
            return False

        # 调用解密（应该直接跳过）
        decrypt_kms_secrets()
        print("✓ decrypt_kms_secrets() 正确跳过解密")

        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_kms_enabled_no_files():
    """测试 KMS 启用但文件不存在时的行为"""
    print("\n" + "=" * 60)
    print("测试 4: KMS 启用但文件不存在")
    print("-" * 60)

    try:
        from bkflow.contrib.kms import decrypt_kms_secrets, is_kms_enabled

        # 模拟 KMS 启用
        os.environ['BKPAAS_KMS_ENABLED'] = 'true'

        # 检查状态
        enabled = is_kms_enabled()
        print(f"  is_kms_enabled() = {enabled}")

        if not enabled:
            print("✗ KMS 应该是启用状态")
            return False

        # 调用解密（应该抛出 FileNotFoundError）
        try:
            decrypt_kms_secrets()
            print("✗ 应该抛出 FileNotFoundError")
            return False
        except FileNotFoundError as e:
            print(f"✓ 正确抛出 FileNotFoundError: {e}")
            return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    finally:
        # 清理环境变量
        if 'BKPAAS_KMS_ENABLED' in os.environ:
            del os.environ['BKPAAS_KMS_ENABLED']


def test_requirements():
    """检查 requirements.txt"""
    print("\n" + "=" * 60)
    print("测试 5: requirements.txt 配置")
    print("-" * 60)

    try:
        import os
        # 获取项目根目录
        project_root = os.path.dirname(os.path.abspath(__file__))
        req_file = os.path.join(project_root, 'requirements.txt')

        with open(req_file, 'r', encoding='utf-8') as f:
            content = f.read()

        if 'bk-kms-sdk[gm]' in content:
            print("✓ requirements.txt 包含 bk-kms-sdk[gm]")
            return True
        else:
            print("✗ requirements.txt 缺少 bk-kms-sdk[gm]")
            return False
    except Exception as e:
        print(f"✗ 读取 requirements.txt 失败: {e}")
        return False


def show_integration_info():
    """显示集成信息"""
    print("\n" + "=" * 60)
    print("KMS 集成信息")
    print("=" * 60)

    print("\n📦 依赖包:")
    print("   - bk-kms-sdk[gm]==1.0.0  # gm 为国密依赖")

    print("\n📝 新增文件:")
    print("   - bkflow/contrib/kms.py         (KMS 解密模块)")
    print("   - bkflow/contrib/kms_example.py (使用示例)")
    print("   - docs/KMS_PAAS_INTEGRATION.md  (集成文档)")

    print("\n⚙️  修改文件:")
    print("   - requirements.txt              (添加 bk-kms-sdk[gm])")

    print("\n🔑 使用方法:")
    print("   from bkflow.contrib.kms import decrypt_kms_secrets")
    print("   decrypt_kms_secrets()  # 在应用入口调用")

    print("\n📚 文档:")
    print("   - 完整文档: docs/KMS_PAAS_INTEGRATION.md")
    print("   - 使用示例: bkflow/contrib/kms_example.py")

    print("\n🚀 平台配置:")
    print("   1. 平台运维开启 PAAS_SAAS_KMS_ENABLED")
    print("   2. 为应用开启「加密运行环境敏感变量」特性")
    print("   3. 在环境变量页面勾选变量为「敏感」")
    print("   4. 完整部署应用")

    print("\n" + "=" * 60)


def main():
    """运行所有测试"""
    print("\n" + "╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "BKFlow KMS 集成测试（PaaS 平台规范）".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")

    tests = [
        ("KMS 模块导入", test_kms_module_import),
        ("bk-kms-sdk 可用性", test_bk_kms_sdk),
        ("KMS 未启用行为", test_kms_disabled),
        ("KMS 启用但无文件", test_kms_enabled_no_files),
        ("requirements.txt", test_requirements),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ 测试 '{test_name}' 执行失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # 显示集成信息
    show_integration_info()

    # 总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    passed = sum(1 for _, r in results if r)
    total = len(results)

    print(f"\n通过: {passed}/{total}")

    if passed == total:
        print("\n🎉 KMS 集成完成！")
        print("\n按照蓝鲸 PaaS 平台规范:")
        print("✓ SDK 安装正确")
        print("✓ 模块实现符合文档要求")
        print("✓ 可以在平台开启 KMS 后使用")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
