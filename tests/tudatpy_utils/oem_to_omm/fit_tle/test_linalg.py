"""Tests for oem_to_omm/linalg.py — Linear algebra utilities for TLE fitting."""

from __future__ import annotations

import numpy as np
import pytest

from oem_to_omm.fit_tle import linalg


class TestSolveLinearSystem:
    """Tests for solve_linear_system function."""

    def test_solve_simple_2x2_system(self) -> None:
        """Should solve a simple 2×2 linear system."""
        # System: 2x + y = 5, x + 3y = 6
        # Solution: x = 1.8, y = 1.4
        matrix = np.array([[2.0, 1.0], [1.0, 3.0]])
        vector = np.array([5.0, 6.0])
        
        solution = linalg.solve_linear_system(matrix, vector)
        
        assert solution is not None
        # Verify solution satisfies the system
        result = matrix @ solution
        np.testing.assert_allclose(result, vector, rtol=1e-10)

    def test_solve_3x3_system(self) -> None:
        """Should solve a 3×3 linear system."""
        # System with known solution [1, 2, 3]
        matrix = np.array([
            [2.0, 1.0, 1.0],
            [1.0, 3.0, 2.0],
            [1.0, 1.0, 4.0]
        ])
        vector = np.array([7.0, 13.0, 15.0])
        
        solution = linalg.solve_linear_system(matrix, vector)
        
        assert solution is not None
        np.testing.assert_allclose(solution, [1.0, 2.0, 3.0], rtol=1e-10)

    def test_solve_identity_system(self) -> None:
        """Should solve identity matrix system."""
        matrix = np.eye(3)
        vector = np.array([1.0, 2.0, 3.0])
        
        solution = linalg.solve_linear_system(matrix, vector)
        
        assert solution is not None
        np.testing.assert_allclose(solution, vector, rtol=1e-10)

    def test_solve_diagonal_system(self) -> None:
        """Should solve diagonal matrix system."""
        matrix = np.diag([2.0, 3.0, 4.0])
        vector = np.array([4.0, 9.0, 16.0])
        
        solution = linalg.solve_linear_system(matrix, vector)
        
        assert solution is not None
        np.testing.assert_allclose(solution, [2.0, 3.0, 4.0], rtol=1e-10)

    def test_solve_with_pivoting(self) -> None:
        """Should handle systems requiring row pivoting."""
        # System that requires pivoting (first element is zero)
        matrix = np.array([
            [0.0, 2.0, 1.0],
            [1.0, 1.0, 2.0],
            [2.0, 1.0, 1.0]
        ])
        vector = np.array([5.0, 8.0, 9.0])
        
        solution = linalg.solve_linear_system(matrix, vector)
        
        assert solution is not None
        # Verify solution satisfies the system
        result = matrix @ solution
        np.testing.assert_allclose(result, vector, rtol=1e-10)

    def test_singular_matrix_returns_none(self) -> None:
        """Should return None for singular matrix."""
        # Singular matrix (rows are linearly dependent)
        matrix = np.array([
            [1.0, 2.0],
            [2.0, 4.0]
        ])
        vector = np.array([3.0, 6.0])
        
        solution = linalg.solve_linear_system(matrix, vector)
        
        assert solution is None

    def test_near_singular_matrix_returns_none(self) -> None:
        """Should return None for near-singular matrix."""
        # Nearly singular matrix
        matrix = np.array([
            [1.0, 2.0],
            [1.0, 2.0 + 1e-16]
        ])
        vector = np.array([3.0, 3.0])
        
        solution = linalg.solve_linear_system(matrix, vector)
        
        assert solution is None

    def test_solve_with_negative_values(self) -> None:
        """Should handle systems with negative values."""
        matrix = np.array([
            [2.0, -1.0],
            [-1.0, 3.0]
        ])
        vector = np.array([1.0, 2.0])
        
        solution = linalg.solve_linear_system(matrix, vector)
        
        assert solution is not None
        result = matrix @ solution
        np.testing.assert_allclose(result, vector, rtol=1e-10)

    def test_solve_large_system(self) -> None:
        """Should solve larger systems efficiently."""
        n = 10
        # Create a well-conditioned positive definite matrix
        A = np.random.rand(n, n)
        matrix = A.T @ A + np.eye(n)
        expected = np.random.rand(n)
        vector = matrix @ expected
        
        solution = linalg.solve_linear_system(matrix, vector)
        
        assert solution is not None
        np.testing.assert_allclose(solution, expected, rtol=1e-8)


class TestSolveWeightedLeastSquares:
    """Tests for solve_weighted_least_squares function."""

    def test_solve_overdetermined_system(self) -> None:
        """Should solve overdetermined least-squares problem."""
        # Fit line y = 2x + 1 through noisy points
        design_matrix = np.array([
            [1.0, 0.0],
            [1.0, 1.0],
            [1.0, 2.0],
            [1.0, 3.0]
        ])
        target_vector = np.array([1.0, 3.0, 5.0, 7.0])
        
        solution = linalg.solve_weighted_least_squares(design_matrix, target_vector)
        
        assert solution is not None
        # Should get approximately [1, 2] (intercept, slope)
        np.testing.assert_allclose(solution, [1.0, 2.0], rtol=1e-10)

    def test_solve_exact_fit(self) -> None:
        """Should solve exactly determined system."""
        # Square system with exact solution
        design_matrix = np.array([
            [1.0, 2.0],
            [3.0, 4.0]
        ])
        target_vector = np.array([5.0, 11.0])
        
        solution = linalg.solve_weighted_least_squares(design_matrix, target_vector)
        
        assert solution is not None
        np.testing.assert_allclose(solution, [1.0, 2.0], rtol=1e-10)

    def test_solve_with_noise(self) -> None:
        """Should find best fit for noisy data."""
        # Generate noisy linear data
        np.random.seed(42)
        x = np.linspace(0, 10, 20)
        design_matrix = np.column_stack([np.ones_like(x), x])
        true_params = np.array([3.0, 2.0])
        target_vector = design_matrix @ true_params + 0.1 * np.random.randn(20)
        
        solution = linalg.solve_weighted_least_squares(design_matrix, target_vector)
        
        assert solution is not None
        # Should be close to true parameters
        np.testing.assert_allclose(solution, true_params, rtol=0.1)

    def test_solve_polynomial_fit(self) -> None:
        """Should fit polynomial to data."""
        # Fit quadratic y = 1 + 2x + 3x²
        x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        design_matrix = np.column_stack([np.ones_like(x), x, x**2])
        target_vector = 1.0 + 2.0 * x + 3.0 * x**2
        
        solution = linalg.solve_weighted_least_squares(design_matrix, target_vector)
        
        assert solution is not None
        np.testing.assert_allclose(solution, [1.0, 2.0, 3.0], rtol=1e-10)

    def test_solve_underdetermined_returns_solution(self) -> None:
        """Should return a solution for underdetermined system."""
        # More parameters than observations
        design_matrix = np.array([
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0]
        ])
        target_vector = np.array([7.0, 8.0])
        
        solution = linalg.solve_weighted_least_squares(design_matrix, target_vector)
        
        # Should return some solution (regularization helps)
        assert solution is not None
        assert len(solution) == 3

    def test_regularization_prevents_singular(self) -> None:
        """Should handle near-singular systems via regularization."""
        # Design matrix with nearly dependent columns
        design_matrix = np.array([
            [1.0, 1.0 + 1e-10],
            [2.0, 2.0 + 2e-10],
            [3.0, 3.0 + 3e-10]
        ])
        target_vector = np.array([1.0, 2.0, 3.0])
        
        solution = linalg.solve_weighted_least_squares(design_matrix, target_vector)
        
        # Should still return a solution due to regularization
        assert solution is not None

    def test_solve_with_multiple_features(self) -> None:
        """Should solve multi-feature regression."""
        # Multiple linear regression
        design_matrix = np.array([
            [1.0, 1.0, 2.0],
            [1.0, 2.0, 3.0],
            [1.0, 3.0, 4.0],
            [1.0, 4.0, 5.0]
        ])
        # y = 1 + 2*x1 + 3*x2
        target_vector = np.array([9.0, 14.0, 19.0, 24.0])
        
        solution = linalg.solve_weighted_least_squares(design_matrix, target_vector)
        
        assert solution is not None
        # Should be close to [1, 2, 3] but regularization may cause small differences
        np.testing.assert_allclose(solution, [1.0, 2.0, 3.0], rtol=0.02)

    def test_solve_with_zero_target(self) -> None:
        """Should handle zero target vector."""
        design_matrix = np.array([
            [1.0, 2.0],
            [3.0, 4.0],
            [5.0, 6.0]
        ])
        target_vector = np.zeros(3)
        
        solution = linalg.solve_weighted_least_squares(design_matrix, target_vector)
        
        assert solution is not None
        # Should get near-zero solution
        np.testing.assert_allclose(solution, [0.0, 0.0], atol=1e-10)

    def test_solve_large_overdetermined_system(self) -> None:
        """Should efficiently solve large overdetermined systems."""
        np.random.seed(123)
        m, n = 100, 5
        design_matrix = np.random.randn(m, n)
        true_params = np.random.randn(n)
        target_vector = design_matrix @ true_params + 0.01 * np.random.randn(m)
        
        solution = linalg.solve_weighted_least_squares(design_matrix, target_vector)
        
        assert solution is not None
        np.testing.assert_allclose(solution, true_params, rtol=0.1)
