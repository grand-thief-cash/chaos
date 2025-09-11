package pipeline

import (
	"github.com/grand-thief-cash/chaos/app/infra/utils_go/channels"
	"sync"
)

type Node struct {
	Name    string
	Inputs  []<-chan any // multi inputs
	Output  chan any     // 下游输出
	Task    Task         // 加工任务
	Workers int          // parallel workers (>=1)

}

func NewNode(name string, task Task) *Node {
	return &Node{
		Name:    name,
		Output:  make(chan any),
		Task:    task,
		Workers: 1,
	}
}
func NewNodeWithSource(name string, task Task, input <-chan any) *Node {
	return &Node{
		Name:    name,
		Inputs:  []<-chan any{input},
		Output:  make(chan any),
		Task:    task,
		Workers: 1,
	}
}

func NewNodeWithSourceParallel(name string, task Task, input <-chan any, workers int) *Node {
	if workers <= 0 {
		workers = 1
	}
	return &Node{
		Name:    name,
		Inputs:  []<-chan any{input},
		Output:  make(chan any),
		Task:    task,
		Workers: workers,
	}
}

func (n *Node) Run(done <-chan struct{}) {
	// Merge inputs once; shared by all workers.
	in := channels.Merge(done, n.Inputs...)

	workers := n.Workers
	if workers <= 0 {
		workers = 1
	}

	var wg sync.WaitGroup
	wg.Add(workers)

	for i := 0; i < workers; i++ {
		go func() {
			defer wg.Done()
			for {
				select {
				case <-done:
					return
				case data, ok := <-in:
					if !ok {
						return
					}
					result, err := n.Task.Process(data)
					if err != nil {
						continue
					}
					select {
					case <-done:
						return
					case n.Output <- result:
					}
				}
			}
		}()
	}

	// Close output after all workers finish.
	go func() {
		wg.Wait()
		close(n.Output)
	}()
}
