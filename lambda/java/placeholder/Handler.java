package seng533.lambda.java.placeholder;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;

import software.amazon.awssdk.core.ResponseBytes;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;

import java.util.Map;

public class Handler implements RequestHandler<Map<String, Object>, Map<String, Object>> {

    private static final String BUCKET = "seng533-lambda-performance-evaluation-assets";
    private static final String KEY = "test-object.txt";

    private static final S3Client s3 = S3Client.create();

    @Override
    public Map<String, Object> handleRequest(Map<String, Object> event, Context context) {

        try {
            int totalBytes = 0;

            // Perform 3 S3 reads (for stability)
            for (int i = 0; i < 3; i++) {
                GetObjectRequest request = GetObjectRequest.builder()
                        .bucket(BUCKET)
                        .key(KEY)
                        .build();

                ResponseBytes<GetObjectResponse> objectBytes = s3.getObjectAsBytes(request);
                totalBytes += objectBytes.asByteArray().length;
            }

            return Map.of(
                    "statusCode", 200,
                    "bytesRead", totalBytes
            );

        } catch (Exception e) {
            context.getLogger().log("Error: " + e.getMessage());

            return Map.of(
                    "statusCode", 500,
                    "error", e.getMessage()
            );
        }
    }
}