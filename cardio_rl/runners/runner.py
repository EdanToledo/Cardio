import copy
import logging
from typing import Optional

import numpy as np
import cardio_rl as crl
from tqdm import trange
from gymnasium import Env
from cardio_rl import Gatherer, Agent, Transition


class BaseRunner:
    def __init__(
        self,
        env: Env,
        agent: Agent,
        rollout_len: int = 1,
        warmup_len: int = 1_000,
        gatherer: Optional[Gatherer] = None,
        n_step: int = 1
    ) -> None:
        self.env = env
        self.eval_env = copy.deepcopy(env)
        self.rollout_len = rollout_len
        self.warmup_len = warmup_len

        if gatherer is None:
            self.gatherer: Gatherer = Gatherer(n_step=n_step)
        else:
            self.gatherer = gatherer

        self.n_step = n_step
        self.agent = agent
        self.agent.setup(self.env)

        self.gatherer._init_env(self.env)
        # self._burn_in(10_000) # TODO: implement propoerly with argument
        self.gatherer.reset()

        # Logging should only start now
        if self.warmup_len:
            self._warm_start()

    def _burn_in(self, length: int) -> None:
        dummy = Agent()
        dummy.setup(self.env)
        self.gatherer.step(dummy, length)

    def _rollout(self, length: int) -> Transition:
        rollout_batch = self.gatherer.step(self.agent, length)
        return crl.tree.stack(rollout_batch)

    def _warm_start(self):
        # Need to figure out whether to perform a random policy or not during warmup
        self._rollout(self.warmup_len)
        logging.info("### Warm up finished ###")

    def step(self) -> list[Transition]:
        rollout_batch = self._rollout(self.rollout_len)
        batch_samples = self.prep_batch(rollout_batch)
        return [batch_samples]

    def run(
        self,
        rollouts: int = 1_000_000,
        eval_interval: int = 10_000,
        eval_episodes: int = 100,
    ) -> None:
        steps = 0

        for i in trange(rollouts):
            if i % eval_interval == 0 and i > 0:
                metrics = self.evaluate(eval_episodes)
                metrics.update({"steps": steps})
            
            data = self.step()
            self.agent.update(data)
            steps += self.rollout_len

    def evaluate(self, episodes: int) -> dict:
        metrics = {"return": np.zeros(episodes), "length": np.zeros(episodes)}
        for e in range(episodes):
            state, _ = self.eval_env.reset()
            returns = 0.0
            steps: int = 0
            while True:
                action, _ = self.agent.eval_step(state)
                next_state, reward, done, trun, _ = self.eval_env.step(action)
                returns += reward  # type: ignore
                steps += 1
                state = next_state
                if done or trun:
                    metrics["return"][e] = returns
                    metrics["length"][e] = steps
                    break

        return metrics

    def update_agent(self, new_agent: Agent, setup=False):
        self.agent = new_agent
        if setup:
            self.agent.setup(self.env)

    def prep_batch(self, batch: dict) -> dict:
        if self.n_step > 1:
            batch['r'] = np.transpose(batch['r'])
        return batch

    def reset(self) -> None:
        self.gatherer.reset()
