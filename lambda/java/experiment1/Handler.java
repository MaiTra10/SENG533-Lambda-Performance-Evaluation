package seng533.lambda.java.experiment1;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import java.util.Map;
import java.util.Random;

public class Handler implements RequestHandler<Map<String, Object>, String> {
    @Override
    public String handleRequest(Map<String, Object> input, Context context) {
        //run test functions in here
        return "Hello from Lambda!";
    }

    public void matrix_mult () {
        Random rand = new Random();

        //generate random matrix dimensions
        int A_rows = rand.nextInt(11) + 90; //90-100
        int A_cols = rand.nextInt(11) + 90;
        int B_rows = A_cols;
        int B_cols  = rand.nextInt(11) + 100; //100-110

        //generate random matrices
        int[][] A = new int[A_rows][A_cols];
        for (int i = 0; i < A_rows; i++){
            for (int j = 0; j < A_cols; j++){
                A[i][j] = rand.nextInt(128);
            }
        }

        int[][] B = new int[B_rows][B_cols];
        for (int i = 0; i < B_rows; i++){
            for (int j = 0; j < B_cols; j++){
                B[i][j] = rand.nextInt(128);
            }
        }

        //allocate result matrix
        int[][] result = new int[A_rows][B_cols];

        //perform multiplication
        for (int x = 0; x < A_rows; x++) {
            for (int y = 0; y < B_cols; y++) {
                for (int z = 0; z < B_rows; z++) {
                    result[x][y] += A[x][z] * B[z][y];
                }
            }
        }
    }
}