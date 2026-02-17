import argparse

import uvicorn

from artemis.api.http_gateway.routes import app  # registers tasks
from artemis.core import cfg_mgr
from artemis.log.logger import reconfigure_logging


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description='Start Artemis data pulling HTTP gateway.'
    )
    parser.add_argument('-c', '--config', dest='config', help='Path to config.yaml', default=None)
    parser.add_argument('-e', '--env', dest='env', help='Environment name (development|staging|production)', default=None)
    return parser

if __name__ == '__main__':
    parser = build_arg_parser()
    args = parser.parse_args()
    cfg_mgr.init_config(path=args.config, env=args.env)
    reconfigure_logging()
    cfg = cfg_mgr.get_config()
    server_cfg = cfg.server
    host = server_cfg.host
    port = server_cfg.port
    uvicorn.run(app, host=host, port=port, access_log=False)
