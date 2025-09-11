package pipeline

type Pipeline struct {
	Nodes    []*Node
	Input    chan any // 入口
	Output   chan any // 出口
	NodesMap map[string]*Node
}

func NewPipeline() *Pipeline {
	return &Pipeline{
		Input:    make(chan any),
		Output:   make(chan any),
		NodesMap: make(map[string]*Node),
	}
}

func (p *Pipeline) AddSource(node *Node, input chan any) {
	node.Inputs = []<-chan any{input}
	p.Nodes = append(p.Nodes, node)
}

func (p *Pipeline) AddStage(node *Node, upstreams ...*Node) {
	if node.Name == "" {
		panic("node name is empty")
	}
	if _, exists := p.NodesMap[node.Name]; exists {
		panic("node with the same name already exists: " + node.Name)
	}
	if len(upstreams) == 0 && (node.Inputs == nil || len(node.Inputs) == 0) {
		panic("node has no upstreams and no input")
	}
	// register node
	p.NodesMap[node.Name] = node

	// connect upstreams
	for _, up := range upstreams {
		node.Inputs = append(node.Inputs, up.Output)
	}

	p.Nodes = append(p.Nodes, node)
	p.Output = node.Output // update pipeline output to the last added node's output
}

func (p *Pipeline) Run(done <-chan struct{}) {
	for _, n := range p.Nodes {
		n.Run(done)
	}
}
