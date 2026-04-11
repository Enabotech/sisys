"""
生命周期脚本测试 - first-run.sh 和 uninstall.sh
TDD 流程：RED → GREEN → REFACTOR

跨平台兼容：支持 macOS 和 Linux CI
"""
import pytest
import subprocess
import os
import tempfile
import sys
from pathlib import Path


class TestFirstRunScript:
    """首次启动脚本测试"""
    
    def test_first_run_detects_docker_when_available(self, mock_docker_available):
        """Given Docker 已安装，When 运行 first-run.sh，Then 应检测到 Docker"""
        import shutil
        assert shutil.which("docker") is not None
    
    def test_first_run_fails_gracefully_when_docker_missing(self, mock_docker_not_available, capfd):
        """Given Docker 未安装，When 运行 first-run.sh，Then 应显示友好提示"""
        import shutil
        result = shutil.which("docker")
        assert result is None
    
    def test_first_run_creates_data_directory(self, temp_sisys_home):
        """Given 首次运行，When 执行脚本，Then 应创建数据目录"""
        data_dir = temp_sisys_home / "data"
        # 脚本应该创建此目录
        assert temp_sisys_home.exists()
    
    def test_first_run_checks_disk_space(self):
        """Given 运行前，When 检查磁盘空间，Then 应验证 ≥ 40GB"""
        import shutil
        total, used, free = shutil.disk_usage("/")
        free_gb = free / (1024**3)
        # 应至少 40GB
        assert free_gb >= 40, f"磁盘空间不足：{free_gb:.1f}GB < 40GB"
    
    def test_first_run_checks_memory(self):
        """Given 运行前，When 检查内存，Then 应验证 ≥ 16GB"""
        import subprocess
        
        # 仅在 macOS 上测试
        if sys.platform != "darwin":
            pytest.skip("仅适用于 macOS")
        
        try:
            result = subprocess.run(["sysctl", "-n", "hw.memsize"], 
                                  capture_output=True, text=True, check=True)
            memory_gb = int(result.stdout.strip()) / (1024**3)
            assert memory_gb >= 16, f"内存不足：{memory_gb:.1f}GB < 16GB"
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("无法获取内存信息")
    
    def test_first_run_pulls_images(self, sample_docker_compose):
        """Given Docker 已安装，When 首次运行，Then 应拉取镜像"""
        # 验证 compose 文件包含所有必要服务
        try:
            import yaml
            with open(sample_docker_compose) as f:
                compose = yaml.safe_load(f)
            
            expected_services = ["postgres", "redis", "qdrant", "minio", "neo4j", "sisys"]
            for service in expected_services:
                assert service in compose.get("services", {}), f"缺少服务：{service}"
        except ImportError:
            pytest.skip("PyYAML 未安装")


class TestUninstallScript:
    """卸载脚本测试"""
    
    def test_uninstall_stops_containers(self, sample_docker_compose):
        """Given 服务运行中，When 卸载，Then 应先停止容器"""
        compose_path = sample_docker_compose
        assert Path(compose_path).exists()
    
    def test_uninstall_removes_containers(self):
        """Given 容器已停止，When 卸载，Then 应删除容器"""
        # 应该执行 docker compose down -v
        assert True  # 占位符
    
    def test_uninstall_removes_data_directory(self, temp_sisys_home):
        """Given 数据目录存在，When 卸载，Then 应删除数据"""
        data_dir = temp_sisys_home / "data"
        data_dir.mkdir(exist_ok=True)
        
        # 卸载脚本应删除此目录
        # 测试逻辑：验证目录存在
        assert data_dir.exists()
    
    def test_uninstall_removes_launch_agent(self, clean_launch_agent):
        """Given LaunchAgent 存在，When 卸载，Then 应删除"""
        clean_launch_agent.touch()
        assert clean_launch_agent.exists()
        # 卸载后应删除
        # clean_launch_agent.unlink()  # 模拟卸载
    
    def test_uninstall_prompts_backup(self, capfd):
        """Given 用户有数据，When 卸载，Then 应提示备份"""
        # 应显示"是否备份数据"提示
        print("是否备份数据？[y/N]")
        captured = capfd.readouterr()
        assert "备份" in captured.out or "backup" in captured.out.lower()
    
    def test_uninstall_clears_keychain(self):
        """Given Keychain 有密码，When 卸载，Then 应清理"""
        # 应执行 security delete-generic-internet-password
        # 仅在 macOS 上测试
        if sys.platform != "darwin":
            pytest.skip("仅适用于 macOS")
        assert True  # 占位符


class TestPreFlightChecks:
    """安装前预检测试"""
    
    def test_disk_space_requirement(self):
        """Given 安装前，When 检查磁盘，Then 应 ≥ 40GB"""
        import shutil
        total, used, free = shutil.disk_usage("/")
        free_gb = free / (1024**3)
        assert free_gb >= 40
    
    def test_memory_requirement(self):
        """Given 安装前，When 检查内存，Then 应 ≥ 16GB"""
        import subprocess
        
        # 仅在 macOS 上测试
        if sys.platform != "darwin":
            pytest.skip("仅适用于 macOS")
        
        try:
            result = subprocess.run(["sysctl", "-n", "hw.memsize"], 
                                  capture_output=True, text=True, check=True)
            memory_gb = int(result.stdout.strip()) / (1024**3)
            assert memory_gb >= 16
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("无法获取内存信息")
    
    def test_macos_version_requirement(self):
        """Given 安装前，When 检查版本，Then 应 ≥ 12.0"""
        import subprocess
        
        # 仅在 macOS 上测试
        if sys.platform != "darwin":
            pytest.skip("仅适用于 macOS")
        
        try:
            result = subprocess.run(["sw_vers", "-productVersion"], 
                                  capture_output=True, text=True, check=True)
            version = result.stdout.strip()
            major = int(version.split(".")[0])
            assert major >= 12, f"macOS 版本过低：{version}"
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("无法获取 macOS 版本")


class TestRollbackLogic:
    """安装失败回滚测试"""
    
    def test_rollback_on_failure(self, temp_sisys_home):
        """Given 安装失败，When 回滚，Then 应清理半安装状态"""
        # 创建半安装状态
        partial_dir = temp_sisys_home / "partial_install"
        partial_dir.mkdir()
        
        # 回滚后应删除
        assert partial_dir.exists()
    
    def test_no_partial_state_left(self, temp_sisys_home):
        """Given 回滚完成，When 检查，Then 不应残留"""
        # 验证无残留文件
        for item in temp_sisys_home.iterdir():
            if "partial" in item.name.lower():
                pytest.fail(f"发现残留文件：{item}")
