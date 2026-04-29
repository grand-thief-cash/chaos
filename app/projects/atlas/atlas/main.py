"""Atlas — Industry Chain Knowledge Graph Engine entry point."""
import argparse
import uvicorn
from atlas.api.routes import app
from atlas.core.config import load_config


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Start Atlas Knowledge Graph Engine."
    )
    parser.add_argument("-c", "--config", dest="config",
                        help="Path to atlas.yaml", default="config/atlas.yaml")
    return parser


if __name__ == "__main__":
    parser = build_arg_parser()
    args = parser.parse_args()
    cfg = load_config(args.config)
    uvicorn.run(
        app,
        host=cfg["server"]["host"],
        port=cfg["server"]["port"],
        access_log=False,
    )

