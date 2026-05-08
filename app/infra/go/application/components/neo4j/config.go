package neo4j

// Config holds the configuration for Neo4j driver.
type Config struct {
	Enabled               bool   `yaml:"enabled" json:"enabled"`
	URI                   string `yaml:"uri" json:"uri"`                                           // bolt://host:7687
	Username              string `yaml:"username" json:"username"`                                 // auth username
	Password              string `yaml:"password" json:"password"`                                 // auth password
	Database              string `yaml:"database" json:"database"`                                 // target database (default "neo4j")
	MaxConnectionPoolSize int    `yaml:"max_connection_pool_size" json:"max_connection_pool_size"` // connection pool cap
	Encrypted             bool   `yaml:"encrypted" json:"encrypted"`                               // TLS on/off
}

func setDefaults(c *Config) {
	if c.URI == "" {
		c.URI = "bolt://localhost:7687"
	}
	if c.Database == "" {
		c.Database = "neo4j"
	}
	if c.MaxConnectionPoolSize <= 0 {
		c.MaxConnectionPoolSize = 50
	}
}

