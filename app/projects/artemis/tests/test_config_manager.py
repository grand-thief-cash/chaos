import textwrap
from pathlib import Path

from artemis.core.config_manager import ConfigManager


def _write_yaml(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


class TestConfigManagerMerging:
    def test_env_override_deep_merges_nested_sections(self, tmp_path: Path):
        config_dir = tmp_path / "cfg"
        config_dir.mkdir(parents=True, exist_ok=True)

        base_path = config_dir / "config.yaml"
        override_path = config_dir / "config-production.yaml"

        _write_yaml(
            base_path,
            """
            env: development
            server:
              host: 127.0.0.1
              port: 18000
              access_log: false
            dept_services:
              cronjob:
                host: 127.0.0.1
                port: 9999
              phoenixA:
                host: 127.0.0.1
                port: 18085
            data_options:
              asset_types:
                - value: stock
                  label: 股票
              markets:
                - value: zh_a
                  label: A股
              periods:
                - value: daily
                  label: 日线
              adjust_rules:
                - asset_type: stock
                  options:
                    - value: nf
                      label: 不复权
            engine:
              cache_engine:
                enabled: true
                cache_dir: ./cache/artemis
                partition_rules:
                  - match: {}
                    granularity: yearly
            """,
        )
        _write_yaml(
            override_path,
            """
            server:
              port: 19000
            dept_services:
              phoenixA:
                host: 10.0.0.8
            data_options:
              periods:
                - value: weekly
                  label: 周线
            """,
        )

        mgr = ConfigManager()
        cfg = mgr.init_config(path=str(base_path), env="production", force=True)

        assert cfg.server.host == "127.0.0.1"
        assert cfg.server.port == 19000
        assert cfg.server.access_log is False

        assert cfg.dept_services.cronjob.host == "127.0.0.1"
        assert cfg.dept_services.cronjob.port == 9999
        assert cfg.dept_services.phoenixA.host == "10.0.0.8"
        assert cfg.dept_services.phoenixA.port == 18085

        assert [opt.value for opt in cfg.data_options.asset_types] == ["stock"]
        assert [opt.value for opt in cfg.data_options.markets] == ["zh_a"]
        assert [opt.value for opt in cfg.data_options.periods] == ["weekly"]
        assert cfg.engine.cache_engine.enabled is True
        assert cfg.engine.cache_engine.cache_dir == "./cache/artemis"


class TestConfigManagerSourceReload:
    def test_reinit_clears_scanned_sources_cache(self, tmp_path: Path):
        cfg_dir_a = tmp_path / "cfg_a"
        cfg_dir_b = tmp_path / "cfg_b"
        cfg_dir_a.mkdir(parents=True, exist_ok=True)
        cfg_dir_b.mkdir(parents=True, exist_ok=True)

        _write_yaml(
            cfg_dir_a / "config.yaml",
            """
            env: development
            dept_services:
              phoenixA:
                host: 127.0.0.1
                port: 18085
            """,
        )
        _write_yaml(
            cfg_dir_a / "config-home.yaml",
            """
            dept_services:
              phoenixA:
                host: 192.168.31.72
                port: 8085
            """,
        )
        _write_yaml(
            cfg_dir_a / "config-production.yaml",
            """
            dept_services:
              phoenixA:
                host: 192.168.31.142
                port: 8085
            """,
        )

        _write_yaml(
            cfg_dir_b / "config.yaml",
            """
            env: development
            dept_services:
              phoenixA:
                host: 10.10.10.10
                port: 28085
            """,
        )

        mgr = ConfigManager()
        mgr.init_config(path=str(cfg_dir_a / "config.yaml"), env="development", force=True)
        first = mgr.available_sources()
        assert set(first["sources"]) == {"relx", "home", "production"}
        assert first["current"] == "relx"

        mgr.init_config(path=str(cfg_dir_b / "config.yaml"), env="development", force=True)
        second = mgr.available_sources()
        assert second["sources"] == ["relx"]
        assert second["current"] == "relx"

