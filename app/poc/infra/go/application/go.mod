// app/poc_go/go.mod
module github.com/grand-thief-cash/chaos/app/poc/infra/go/application

go 1.23.0

require (
	github.com/go-chi/chi/v5 v5.2.3
	github.com/grand-thief-cash/chaos/app/infra/go/application v0.0.0
	github.com/grand-thief-cash/chaos/app/infra/go/common v0.0.0-00010101000000-000000000000
	google.golang.org/grpc v1.75.1
)

require (
	filippo.io/edwards25519 v1.1.0 // indirect
	github.com/cespare/xxhash/v2 v2.3.0 // indirect
	github.com/dgryski/go-rendezvous v0.0.0-20200823014737-9f7001d12a5f // indirect
	github.com/go-sql-driver/mysql v1.9.3 // indirect
	github.com/google/uuid v1.6.0 // indirect
	github.com/redis/go-redis/v9 v9.14.0 // indirect
	go.uber.org/multierr v1.10.0 // indirect
	go.uber.org/zap v1.26.0 // indirect
	golang.org/x/net v0.41.0 // indirect
	golang.org/x/sys v0.33.0 // indirect
	golang.org/x/text v0.26.0 // indirect
	google.golang.org/genproto/googleapis/rpc v0.0.0-20250707201910-8d1bb00bc6a7 // indirect
	google.golang.org/protobuf v1.36.9 // indirect
	gopkg.in/natefinch/lumberjack.v2 v2.2.1 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
)

replace github.com/grand-thief-cash/chaos/app/infra/go/application => ./../../../../infra/go/application

replace github.com/grand-thief-cash/chaos/app/infra/go/common => ./../../../../infra/go/common
