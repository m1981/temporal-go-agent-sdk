package interfaces

import "context"

//go:generate mockgen -destination=./mocks/mock_retriever.go -package=mocks github.com/m1981/temporal-go-agent-sdk/pkg/interfaces Retriever

type Retriever interface {
	// Name returns the unique name of the retriever.
	Name() string
	// Search searches the retriever for documents matching the query.
	Search(ctx context.Context, query string) ([]Document, error)
}

type Document struct {
	Content  string
	Source   string
	Score    float64
	Metadata map[string]any
}
