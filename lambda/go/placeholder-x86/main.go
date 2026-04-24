package main

import (
	"context"
	"io"
	"log"

	"github.com/aws/aws-lambda-go/lambda"

	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

type Response struct {
	StatusCode int `json:"statusCode"`
}

var (
	bucket = "seng533-aksh-rohil-1-lambda-performance-evaluation-assets"
	key    = "test-object.txt"
)

func handler(ctx context.Context) (Response, error) {

	cfg, err := config.LoadDefaultConfig(ctx)
	if err != nil {
		log.Println("config error:", err)
		return Response{StatusCode: 500}, err
	}

	client := s3.NewFromConfig(cfg)

	// perform 3 reads for stability
	for i := 0; i < 3; i++ {
		resp, err := client.GetObject(ctx, &s3.GetObjectInput{
			Bucket: &bucket,
			Key:    &key,
		})
		if err != nil {
			log.Println("S3 error:", err)
			return Response{StatusCode: 500}, err
		}

		_, err = io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			log.Println("read error:", err)
			return Response{StatusCode: 500}, err
		}
	}

	return Response{StatusCode: 200}, nil
}

func main() {
	lambda.Start(handler)
}