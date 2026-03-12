package main

import (
	"context"

	"github.com/aws/aws-lambda-go/lambda"
)

func main() {
	lambda.Start(placeholder)
}

type Response struct {
	StatusCode int    `json:"statusCode"`
	Body       string `json:"body"`
}

func placeholder(ctx context.Context) (Response, error) {
	return Response{
		StatusCode: 200,
		Body:       "placeholder",
	}, nil
}
