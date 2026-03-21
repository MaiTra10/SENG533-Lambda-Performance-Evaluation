package main

import (
	"context"

	"github.com/aws/aws-lambda-go/lambda"

	"math/rand/v2"
)

func main() {
	lambda.Start(placeholder)
}

type Response struct {
	StatusCode int `json:"statusCode"`
}

func placeholder(ctx context.Context) (Response, error) {
	//generate random matrix dimensions
	A_rows := rand.IntN(11) + 90
	A_cols := rand.IntN(11) + 90
	B_rows := A_cols
	B_cols := rand.IntN(11) + 100

	//generate random matrices
	A := make([][]int, A_rows)
	for i := range A {
		A[i] = make([]int, A_cols)
		for j := range A[i] {
			A[i][j] = rand.IntN(128)
		}
	}

	B := make([][]int, B_rows)
	for i := range B {
		B[i] = make([]int, B_cols)
		for j := range B[i] {
			B[i][j] = rand.IntN(128)
		}
	}

	//allocate result matrix
	result := make([][]int, A_rows)
	for i := range result {
		result[i] = make([]int, B_cols)
	}

	//perform multiplication
	for x := range A_rows {
		for y := range B_cols {
			for z := range B_rows {
				result[x][y] += A[x][z] * B[z][y]
			}
		}
	}

	return Response{
		StatusCode: 200,
	}, nil
}
