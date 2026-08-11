"""Linear algebra utilities for TLE estimation.

Provides functions for solving dense linear systems and weighted least-squares
problems using Gaussian elimination and normal equations. Designed for small
systems typical in TLE parameter estimation workflows.

References:
    Golub, G.H. and Van Loan, C.F. "Matrix Computations", 4th ed., Johns Hopkins University Press.
    Strang, G. "Introduction to Linear Algebra", 5th ed., Wellesley-Cambridge Press.
"""

from __future__ import annotations

import numpy as np


def solve_linear_system(matrix: np.ndarray, vector: np.ndarray) -> np.ndarray | None:
    """Solve a dense linear system with Gaussian elimination.

    Parameters
    ----------
    matrix : np.ndarray
        Coefficient matrix (n×n).
    vector : np.ndarray
        Right-hand side vector (n,).

    Returns
    -------
    np.ndarray | None
        Solution vector (n,), or None if system is singular.
    """
    matrix = np.asarray(matrix, dtype=float)
    vector = np.asarray(vector, dtype=float)

    size: int = len(vector)  # n
    augmented: np.ndarray = np.column_stack([matrix, vector])  # (n×(n+1))

    for pivot_index in range(size):
        pivot_row: int = pivot_index + np.argmax(
            np.abs(augmented[pivot_index:, pivot_index])
        )
        pivot_value: float = augmented[pivot_row, pivot_index]
        if abs(pivot_value) < 1e-15:
            return None

        if pivot_row != pivot_index:
            augmented[[pivot_index, pivot_row]] = augmented[[pivot_row, pivot_index]]

        pivot_value = augmented[pivot_index, pivot_index]
        augmented[pivot_index, pivot_index:] /= pivot_value

        for row_index in range(size):
            if row_index == pivot_index:
                continue
            factor: float = augmented[row_index, pivot_index]
            augmented[row_index, pivot_index:] -= (
                factor * augmented[pivot_index, pivot_index:]
            )

    return augmented[:, size]  # (n,)


def solve_weighted_least_squares(
    design_matrix: np.ndarray, target_vector: np.ndarray
) -> np.ndarray | None:
    """Solve a small dense least-squares system via normal equations.

    Parameters
    ----------
    design_matrix : np.ndarray
        Design matrix (m×n), m observations × n parameters.
    target_vector : np.ndarray
        Target vector (m,), m observations.

    Returns
    -------
    np.ndarray | None
        Parameter vector (n,), or None if system is singular.
    """
    design_matrix = np.asarray(design_matrix, dtype=float)
    target_vector = np.asarray(target_vector, dtype=float)

    # Compute normal equations: A^T A x = A^T b
    normal_matrix: np.ndarray = design_matrix.T @ design_matrix  # (n×n)
    normal_vector: np.ndarray = design_matrix.T @ target_vector  # (n,)

    # Add regularization to diagonal
    normal_matrix += 1e-12 * np.eye(normal_matrix.shape[0])

    return solve_linear_system(normal_matrix, normal_vector)
