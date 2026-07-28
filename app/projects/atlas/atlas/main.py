import argparse

import uvicorn

from atlas.api.http_gateway.routes import create_app
from atlas.application.runtime import build_runtime
from atlas.core import cfg_mgr


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start Atlas knowledge engine HTTP gateway.")
    parser.add_argument("-c", "--config", dest="config", default=None)
    parser.add_argument("-e", "--env", dest="env", default=None)
    return parser


if __name__ == "__main__":
    args = build_arg_parser().parse_args()
    config = cfg_mgr.init_config(path=args.config, env=args.env)
    app = create_app(build_runtime(config))
    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        access_log=config.server.access_log,
    )
