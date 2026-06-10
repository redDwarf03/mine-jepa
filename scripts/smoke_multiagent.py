"""
Smoke test — does a 2-agent shared-world MineRL mission start and step?

This isolates the fragile part (two Minecraft clients into one Malmo mission) BEFORE
wiring JEPA planners. It prints the obs/action structure so we learn the exact
multi-agent API, then steps both agents with forward+attack for a few ticks.

Usage: run.bat scripts/smoke_multiagent.py
"""
import logging

logging.getLogger("minerl").setLevel(logging.CRITICAL)

import minerl  # noqa: F401 — registers base envs + builds the gym registry
import gym

from mine_jepa.envs import register_multiagent_envs


def main():
    name = register_multiagent_envs(n_agents=2)
    print(f"Registered: {name}", flush=True)

    print("Creating env (this launches 2 Minecraft clients — slow)...", flush=True)
    env = gym.make(name)

    print("Resetting (both clients join the shared world)...", flush=True)
    obs = env.reset()
    print(f"  obs type: {type(obs).__name__}", flush=True)
    print(f"  obs keys (agents): {list(obs.keys())}", flush=True)
    first = list(obs.keys())[0]
    print(f"  {first} obs keys: {list(obs[first].keys())}", flush=True)
    print(f"  {first} pov shape: {obs[first]['pov'].shape}", flush=True)

    noop = env.action_space.no_op()
    print(f"  action no_op keys: {list(noop.keys())}", flush=True)

    print("Stepping 20 ticks (both agents forward+attack)...", flush=True)
    for t in range(20):
        acts = env.action_space.no_op()
        for agent in acts:
            acts[agent]["forward"] = 1
            acts[agent]["attack"] = 1
        obs, reward, done, info = env.step(acts)
        if t == 0:
            print(f"  step ok — reward: {reward}", flush=True)
        if done:
            print(f"  done at t={t}", flush=True)
            break

    env.close()
    print("\nMULTI-AGENT SMOKE OK — 2 JEPA agents can share one world.", flush=True)


if __name__ == "__main__":
    main()
