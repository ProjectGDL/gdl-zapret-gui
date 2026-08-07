
import argparse
import sys

def build_parser():
    p = argparse.ArgumentParser(description="gdl-zapret-gui")
    p.add_argument(
        "--daemon",
        action="store_true",
        help="запустить привилегированный демон zapretd (от root, для systemd)",
    )
    p.add_argument(
        "--data-dir",
        help="каталог данных демона (по умолчанию /var/lib/zapretgd)",
    )
    p.add_argument(
        "--status",
        action="store_true",
        help="показать статус демона и nfqws",
    )
    return p

def run_daemon_mode(data_dir: str | None):
    from gdl_zapret.app_paths import DaemonPaths
    from gdl_zapret.daemon import run_daemon

    paths = DaemonPaths(data_dir)
    run_daemon(paths)

def run_status_mode():
    from gdl_zapret.client import DaemonClient, DaemonUnavailable

    client = DaemonClient()
    try:
        s = client.status()
    except DaemonUnavailable as e:
        print(f"Демон недоступен: {e}")
        sys.exit(1)

    print(f"running:          {s.get('running')}")
    print(f"pid:              {s.get('pid')}")
    print(f"strategy:         {s.get('strategy')}")
    print(f"interface:        {s.get('interface')}")
    print(f"firewall_backend: {s.get('firewall_backend')}")

def run_gui_mode():
    from gdl_zapret.app_paths import ClientPaths
    from gdl_zapret.config import Config
    from gdl_zapret.gui.main_window import run_app

    paths = ClientPaths()
    config = Config(paths).load()
    paths.ensure_dirs()
    sys.exit(run_app(paths, config))

def main():
    args = build_parser().parse_args()

    if args.daemon:
        run_daemon_mode(args.data_dir)
        return

    if args.status:
        run_status_mode()
        return

    run_gui_mode()

if __name__ == "__main__":
    main()
