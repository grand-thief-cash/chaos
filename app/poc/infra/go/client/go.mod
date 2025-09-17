module github.com/grand-thief-cash/chaos/app/poc/infra/go/client

go 1.23.0

replace github.com/grand-thief-cash/chaos/app/infra/go/common => ./../../../../infra/go/common

require (
	github.com/grand-thief-cash/chaos/app/infra/go/common v0.0.0-00010101000000-000000000000
	google.golang.org/grpc v1.75.1
)

require (
	golang.org/x/net v0.41.0 // indirect
	golang.org/x/sys v0.33.0 // indirect
	golang.org/x/text v0.26.0 // indirect
	google.golang.org/genproto/googleapis/rpc v0.0.0-20250707201910-8d1bb00bc6a7 // indirect
	google.golang.org/protobuf v1.36.9 // indirect
)
