"""
Prioritized Experience Replay from 'Prioritized Experience
Replay' for discrete environments.

Paper:
Hyperparameters:
Experiment details:

DQN with double Q-learning, duellining nets

Notes:

To do:
* implement sum tree and compare speed
"""

import gymnasium as gym
import jax
import numpy as np
import torch as th
import torch.nn as nn
from tqdm import trange

import cardio_rl as crl
from cardio_rl.buffers.sumtree_buffer import PrioritisedBuffer as SumtreeBuffer


class Q_critic(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(Q_critic, self).__init__()

        self.net = nn.Sequential(
            nn.Linear(state_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, action_dim),
        )

    def forward(self, state):
        q = self.net(state)
        return q


class PER(crl.Agent):
    def __init__(self, env: gym.Env, beta: float = 0.5):
        self.env = env
        self.beta = beta
        self.critic = Q_critic(4, 2)
        self.targ_critic = Q_critic(4, 2)
        self.targ_critic.load_state_dict(self.critic.state_dict())
        self.update_count = 0
        self.optimizer = th.optim.Adam(self.critic.parameters(), lr=1e-4)

        self.eps = 0.9
        self.min_eps = 0.05
        schedule_steps = 5000
        self.ann_coeff = self.min_eps ** (1 / schedule_steps)

    def update(self, batches):
        data = jax.tree.map(crl.utils.to_torch, batches[0])
        s, a, r, s_p, d = data["s"], data["a"], data["r"], data["s_p"], data["d"]

        q = self.critic(s).gather(-1, a.long())

        a_p = self.critic(s_p).argmax(-1, keepdim=True)
        q_p = self.targ_critic(s_p).gather(-1, a_p.long())
        y = r + 0.99 * q_p * (1 - d)
        error = q - y.detach()

        loss = th.mean((data["w"] * error) ** 2)

        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        self.update_count += 1
        if self.update_count % 1_000 == 0:
            self.targ_critic.load_state_dict(self.critic.state_dict())

        return {"idxs": batches[0]["idxs"], "p": np.abs(error.numpy(force=True) + 1e-8)}

    def step(self, state):
        if np.random.rand() > self.eps:
            th_state = th.from_numpy(state).unsqueeze(0).float()
            action = self.critic(th_state).argmax().detach().numpy()
        else:
            action = self.env.action_space.sample()

        self.eps = max(self.min_eps, self.eps * self.ann_coeff)
        return action, {}


def main():
    env = gym.make("CartPole-v1")
    agent = PER(env)

    # alpha and beta = 0 should reduce to uniform replay buffer

    # buffer = crl.buffers.PrioritisedBuffer(env)
    buffer = SumtreeBuffer(env)

    runner = crl.OffPolicyRunner(
        env,
        agent,
        buffer=buffer,
        rollout_len=4,
        batch_size=32,
    )

    rollouts = 50_000
    runner.run(rollouts)
    return

    for _ in trange(rollouts):
        data = runner.step(agent=agent)
        updated_data = agent.update(data)
        runner.update(updated_data)


if __name__ == "__main__":
    main()
