import abc
import dataclasses
from typing import TYPE_CHECKING, Tuple

import jax
import numpy as onp
from jax import numpy as jnp
from overrides import overrides

from .. import types, utils
from ..core._variable_assignments import VariableAssignments
from . import _linear_utils

if TYPE_CHECKING:
    from .._prepared_factor_graph import PreparedFactorGraph


class NonlinearSolverBase(abc.ABC):
    # For why we have two classes:
    # https://github.com/python/mypy/issues/5374#issuecomment-650656381
    @abc.abstractmethod
    def solve(
        self,
        graph: "PreparedFactorGraph",
        initial_assignments: "VariableAssignments",
    ) -> "VariableAssignments":
        """Run MAP inference on a factor graph."""


@utils.register_dataclass_pytree
@dataclasses.dataclass(frozen=True)
class NonlinearSolverBase(NonlinearSolverBase):
    """Nonlinear solver interface. """

    max_iterations: int = 100
    """Maximum number of iterations."""

    verbose: bool = True
    """Set to `True` to enable printing."""

    def _print(self, *args, **kwargs):
        """Prefixed printing helper. No-op if `verbose` is set to `False`."""
        if self.verbose:
            print(f"[{type(self).__name__}]", *args, **kwargs)


@utils.register_dataclass_pytree
@dataclasses.dataclass(frozen=True)
class _NonlinearSolverState:
    """Standard state passed between nonlinear solve iterations."""

    iterations: int
    assignments: "VariableAssignments"
    cost: float
    residual_vector: jnp.ndarray
    done: bool


@dataclasses.dataclass(frozen=True)
class _InexactStepSolverMixin:
    """Mixin for inexact Newton steps. Currently used by all solvers."""

    inexact_step_eta: float = 1e-1
    """Forcing sequence parameter for inexact Newton steps. CG tolerance is set to
    `eta / iteration #`.

    For reference, see AN INEXACT LEVENBERG-MARQUARDT METHOD FOR LARGE SPARSE NONLINEAR
    LEAST SQUARES, Wright & Holt 1983."""

    def inexact_step_forcing_sequence(self, iterations: int) -> float:
        """Get CGLS tolerance from zero-indexed iteration count."""
        return self.inexact_step_eta / (iterations + 1)


@dataclasses.dataclass(frozen=True)
class _TerminationCriteriaMixin:
    """Mixin for Ceres-style termination criteria."""

    cost_tolerance: float = 1e-4
    """We terminate if `|cost change| / cost <= cost_tolerance`."""

    gradient_tolerance: float = 1e-4
    """We terminate if `norm_inf(x - rplus(x, linear delta)) <= gradient_tolerance`."""

    parameter_tolerance: float = 1e-4
    """We terminate if `norm_2(linear delta)`."""

    def check_convergence(
        self,
        state_prev: _NonlinearSolverState,
        cost_updated: float,
        local_delta_assignments: VariableAssignments,
        negative_gradient: jnp.ndarray,
    ):
        """Check for convergence!"""
        return (
            # Cost tolerance
            jnp.abs(cost_updated - state_prev.cost) / state_prev.cost
            <= self.cost_tolerance
            # Gradient tolerance
            or jnp.max(
                state_prev.assignments.storage
                - _linear_utils.apply_local_deltas(
                    state_prev.assignments,
                    VariableAssignments(
                        storage=negative_gradient,
                        storage_metadata=local_delta_assignments.storage_metadata,
                    ),
                ).storage
            )
            <= self.gradient_tolerance
            # Parameter tolerance
            or jnp.linalg.norm(jnp.abs(local_delta_assignments.storage))
            <= (
                jnp.linalg.norm(state_prev.assignments.storage)
                + self.parameter_tolerance
            )
            * self.parameter_tolerance
        )
