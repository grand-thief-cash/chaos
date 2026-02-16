import argparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from artemis.api.http_gateway.routes import router  # registers tasks
from artemis.core import cfg_mgr
from artemis.log.logger import reconfigure_logging
from artemis.telemetry.middleware import add_trace_id_middleware
from artemis.telemetry.otel import instrument_fastapi_app, init_otel

app = FastAPI(title='Artemis Gateway')

# 初始化 OTEL（如果配置启用），并对 FastAPI App 做自动 instrumentation
init_otel()
instrument_fastapi_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 X-Trace-Id middleware，确保所有请求都带有可追踪的 trace_id
add_trace_id_middleware(app)

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
    cfg_mgr.init_config(path=args.config, env=args.env)
    reconfigure_logging()
    cfg = cfg_mgr.get_config()
    server_cfg = cfg.server
    host = server_cfg.host
    port = server_cfg.port
    uvicorn.run(app, host=host, port=port, access_log=False)
