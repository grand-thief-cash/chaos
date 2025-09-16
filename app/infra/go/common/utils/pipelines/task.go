package pipelines

type Task interface {
	Process(data any) (any, error)
}
