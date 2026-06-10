"""Custom MineRL environments — multi-agent worlds for JEPA agents.

MineRL 0.4 supports multi-agent missions natively: an EnvSpec with `agent_count=N`
spawns N Minecraft clients into ONE shared world, and step()/reset() become dict-keyed
by agent name ("agent_0", "agent_1", ...). Each JEPA agent drives one of them.

⚠️ N agents = N full Minecraft (JVM) clients. 2 is realistic on a consumer machine;
more strains RAM/GPU. The multi-client Malmo startup is the fragile part.

Usage:
    import minerl                       # registers the base envs first
    from mine_jepa.envs import register_multiagent_envs
    name = register_multiagent_envs(n_agents=2)
    env = gym.make(name)               # MineRLTreechopMulti-v0
"""
from __future__ import annotations

import gym

MULTI_TREECHOP = "MineRLTreechopMulti-v0"


def register_multiagent_envs(n_agents: int = 2) -> str:
    """Register a shared-world multi-agent Treechop and return its gym id."""
    from minerl.herobraine.env_specs.treechop_specs import Treechop

    if MULTI_TREECHOP in gym.envs.registry.env_specs:
        return MULTI_TREECHOP
    spec = Treechop(name=MULTI_TREECHOP, agent_count=n_agents)
    spec.register()
    return MULTI_TREECHOP
