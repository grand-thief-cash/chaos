# gRPC 代码生成说明

| 组件             | 作用                                   | 生成文件类型           | 依赖关系                         |
|------------------|--------------------------------------|------------------------|---------------------------------|
| `option go_package` | 指定生成的Go代码包路径和包名             | 影响 `.pb.go` 和 `.grpc.pb.go` 文件中的包声明和import路径 | 影响`--go_out`和`--go-grpc_out`生成代码的包路径和包名 |
| `--go_out`       | 生成proto消息结构体代码                  | `.pb.go`               | 生成的代码包名由`option go_package`决定 |
| `--go-grpc_out`  | 生成gRPC服务相关代码                     | `.grpc.pb.go`          | 生成的代码包名由`option go_package`决定 |
示例1： protoc --go_out=. --go-grpc_out=. app/poc/application/proto/echo.proto

示例2:  protoc --go_out=..\..\..\..\infra\go\common\grpc_gen\poc --go-grpc_out=..\..\..\..\infra\go\common\grpc_gen\poc protos\echo.proto

```protobuf
option go_package = "/;poc";
```
Before the ';' means protoc will generate folders recursively under your specified "go_out" and "go-grpc_out".
After the ';' it implies `import XXX` in the generated code.

