package pipeline

type Task interface {
	Process(data any) (any, error)
}
