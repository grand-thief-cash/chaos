import argparse

from fastapi import FastAPI

import artemis.task_units.examples.long_task  # noqa
# Import task units to populate registry
import artemis.task_units.market.pull_stock_quotes.unit  # noqa
from artemis.api.http_gateway.routes import router  # registers tasks
from artemis.core.config import init_config, get_config
from artemis.log.logger import reconfigure_logging

app = FastAPI(title='Artemis Gateway')
app.include_router(router)

@app.get('/health')
async def health():
    return {'status': 'ok'}


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description='Start Artemis data pulling HTTP gateway.'
    )
    parser.add_argument('-c', '--config', dest='config', help='Path to config.yaml', default=None)
    parser.add_argument('-e', '--env', dest='env', help='Environment name (development|staging|production)', default=None)
    return parser

if __name__ == '__main__':
    import uvicorn
    parser = build_arg_parser()

    args = parser.parse_args()
    init_config(path=args.config, env=args.env)
    reconfigure_logging()
    cfg = get_config()
    server_cfg = cfg.get('server', {}) or {}
    host = server_cfg.get('host', '0.0.0.0')
    port = int(server_cfg.get('port', 8000))
    uvicorn.run(app, host=host, port=port)
