import random

def multiply_matrix():
    #generate random matrix dimensions
    A_rows = random.randint(90,100)
    A_cols = random.randint(90,100)
    B_rows = A_cols
    B_cols = random.randint(100,110)
    
    #generate random matrices
    A = [[random.randint(0,127) for _ in range(A_cols)] for _ in range(A_rows)]
    B = [[random.randint(0,127) for _ in range(B_cols)] for _ in range(B_rows)]

    #allocate result matrix
    result = [[0] * len(B[0]) for _ in range(len(A))]

    #perform multiplication
    for x in range(len(A)):
        for y in range(len(B[0])):
            for z in range(len(B)):
                result[x][y] += A[x][z] * B[z][y]

    return result