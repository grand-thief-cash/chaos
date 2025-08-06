// app/poc_go/go.mod
module github.com/grand-thief-cash/chaos/app/poc_go

go 1.23.0

require (
	github.com/grand-thief-cash/chaos/app/infra/infra_go v0.0.0
	go.uber.org/zap v1.26.0
)

require (
	github.com/google/uuid v1.6.0 // indirect
	go.uber.org/multierr v1.10.0 // indirect
	gopkg.in/natefinch/lumberjack.v2 v2.2.1 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
)

replace github.com/grand-thief-cash/chaos/app/infra/infra_go => ../infra/infra_go
