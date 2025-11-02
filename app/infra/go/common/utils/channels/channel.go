package channels

import "sync"

// Merge Merge multi channels to a single channels
func Merge(done <-chan struct{}, chans ...<-chan any) <-chan any {
	out := make(chan any)

	var wg sync.WaitGroup
	wg.Add(len(chans))

	forward := func(c <-chan any) {
		defer wg.Done()
		for {
			select {
			case <-done:
				return
			case v, ok := <-c:
				if !ok {
					return
				}
				out <- v
			}
		}
	}

	for _, ch := range chans {
		go forward(ch)
	}

	// 等所有输入结束后，关闭 out
	go func() {
		wg.Wait()
		close(out)
	}()

	return out
}
