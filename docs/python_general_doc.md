


# pip install cmd using proxy

pip install -r requirements.txt --proxy http://192.168.31.169:7890


# python dev

## Python install grpc_tools & using it to generate grpc code


```
pip install grpcio grpcio-tools
```

```chatinput
cd {workspace}

python -m grpc_tools.protoc \
--proto_path=protos/pylon/api/heartbeats/v1 \
--python_out=app/generated/py_gen/grpc/internal/heartbeats/v1 \
--grpc_python_out=app/generated/py_gen/grpc/internal/heartbeats/v1 \
heartbeats.proto
```

## Python infrastructure development
1. Developer mode installation (recommended for development):
    ```
   cd app/infra/pyinfra
   pip install -e .
   ```
   
2. Or install directly:
    ```
    pip install app/infra/
    ```
    
3. Publish to PyPI
