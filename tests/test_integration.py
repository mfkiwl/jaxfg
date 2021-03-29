"""Simple pose graph example with two variables."""

from typing import List

import jaxlie
from jax import numpy as jnp

import jaxfg


def test_pose_graph():
    pose_variables = [
        jaxfg.geometry.SE2Variable(),
        jaxfg.geometry.SE2Variable(),
    ]

    factors: List[jaxfg.core.FactorBase] = [
        jaxfg.geometry.PriorFactor.make(
            variable=pose_variables[0],
            mu=jaxlie.SE2.from_xy_theta(0.0, 0.0, 0.0),
            scale_tril_inv=jnp.eye(3),
        ),
        jaxfg.geometry.PriorFactor.make(
            variable=pose_variables[1],
            mu=jaxlie.SE2.from_xy_theta(2.0, 0.0, 0.0),
            scale_tril_inv=jnp.eye(3),
        ),
        jaxfg.geometry.BetweenFactor.make(
            variable_T_world_a=pose_variables[0],
            variable_T_world_b=pose_variables[1],
            T_a_b=jaxlie.SE2.from_xy_theta(1.0, 0.0, 0.0),
            scale_tril_inv=jnp.eye(3),
        ),
    ]

    graph = jaxfg.core.StackedFactorGraph.make(factors)
    initial_assignments = jaxfg.core.VariableAssignments.make_from_defaults(
        pose_variables
    )

    solution_assignments = graph.solve(initial_assignments)

    assert type(repr(solution_assignments)) == str
    assert isinstance(solution_assignments.get_value(pose_variables[0]), jaxlie.SE2)
    assert isinstance(
        solution_assignments.get_stacked_value(jaxfg.geometry.SE2Variable), jaxlie.SE2
    )
    assert jnp.all(
        solution_assignments.get_value(pose_variables[0]).parameters()
        == solution_assignments.get_stacked_value(
            jaxfg.geometry.SE2Variable
        ).parameters()[0]
    )
    assert jnp.all(
        solution_assignments.get_value(pose_variables[1]).parameters()
        == solution_assignments.get_stacked_value(
            jaxfg.geometry.SE2Variable
        ).parameters()[1]
    )
