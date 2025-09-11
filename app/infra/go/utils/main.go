package main

import (
	"fmt"
	pl "github.com/grand-thief-cash/chaos/app/infra/go/utils/pipeline"
	_ "time"
)

type PassTask struct{}

func (PassTask) Process(data any) (any, error) {
	return data, nil
}

type DoubleTask struct{}

func (DoubleTask) Process(data any) (any, error) {
	if v, ok := data.(int); ok {
		return v * 2, nil
	}
	return nil, fmt.Errorf("not int")
}

func main() {
	done := make(chan struct{})
	pipeline := pl.NewPipeline()

	src1 := make(chan any)
	src2 := make(chan any)
	node1 := pl.NewNodeWithSource("src1", PassTask{}, src1)
	node2 := pl.NewNodeWithSource("src2", PassTask{}, src2)

	// fan-in 节点
	node3 := pl.NewNode("double", DoubleTask{})

	pipeline.AddStage(node1)
	pipeline.AddStage(node2)
	pipeline.AddStage(node3, node1, node2) // fan-in: double 接收 src1 和 src2

	pipeline.Run(done)

	go func() {
		for i := 1; i <= 1; i++ {
			src1 <- i
			src2 <- i * 10
		}
		close(src1)
		close(src2)
	}()

	// 消费结果
	for res := range pipeline.Output {
		fmt.Println("result:", res)
	}

	close(done)
}
