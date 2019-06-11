# https://scipy-lectures.org/advanced/scipy_sparse/coo_matrix.html

import numpy as np
from scipy import sparse
mtx = sparse.coo_matrix((3, 4), dtype=np.int8)
print(mtx, '1')
mtx.todense()
print(mtx)
print("hello")
mtx
# pas d'affichage de la matrice dans la console



# https://machinelearningmastery.com/sparse-matrices-for-machine-learning/

# dense to sparse
from numpy import array
from scipy.sparse import csr_matrix

# create dense matrix
A = array([[1, 0, 0, 1, 0, 0], [0, 0, 2, 0, 0, 1], [0, 0, 0, 2, 0, 0]])
print(A)
# convert to sparse matrix (CSR method)
#S = csr_matrix(A)
#print(S)
# reconstruct dense matrix
#B = S.todense()
#print(B)

print("\nMatrice et calcul sparsity")
# calculate sparsity
from numpy import array
from numpy import count_nonzero

# create dense matrix
A = array([[1, 0, 0, 1, 0, 0], [0, 0, 2, 0, 0, 1], [0, 0, 0, 2, 0, 0]])
print(A)
# calculate sparsity
sparsity = 1.0 - count_nonzero(A) / A.size
print(sparsity)


# https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csr_matrix.html

# Deux facons de construire une matrice CSR
# 1) la version de la video

print("\nConstruction d'une matrice avec pointeurs de début de ligne")
data = [1,1,2,1,2]  # data dans l'ordre lecture classique
indices = [0,3,2,5,3]  # column
indptr = [0,2,4,5] # en rajoutant 5 ça marche, mais je ne sais pas trop pourquoi

F = csr_matrix((data, indices, indptr), shape=(3,6)).toarray()
print(F)

# 2) la methode avec les coordonnees

row = [0,2,3,3,5]
column = [0,0,1,1,2]
data = [1,1,2,1,2]


