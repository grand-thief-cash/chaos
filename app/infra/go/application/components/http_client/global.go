package http_client

import (
	"sync"
)

var (
	gMu      sync.RWMutex
	gClients *HTTPClientsComponent
)

func SetGlobalHTTPClients(c *HTTPClientsComponent) {
	gMu.Lock()
	gClients = c
	gMu.Unlock()
}

func Global() *HTTPClientsComponent {
	gMu.RLock()
	c := gClients
	gMu.RUnlock()
	return c
}

func Client(name string) *InstrumentedClient {
	c := Global()
	if c == nil {
		return nil
	}
	cli, _ := c.Client(name)
	return cli
}

func Default() *InstrumentedClient {
	c := Global()
	if c == nil {
		return nil
	}
	cli, _ := c.Default()
	return cli
}
