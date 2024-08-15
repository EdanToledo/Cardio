import gymnasium as gym
import jax
import numpy as np
import torch as th
import torch.nn as nn

import cardio_rl as crl


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


class DQN(crl.Agent):
    def __init__(self, env: gym.Env):
        self.env = env
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
        data = jax.tree.map(
            th.from_numpy, batches[0]
        )  # TODO: change all other implementations to this
        s, a, r, s_p, d = data["s"], data["a"], data["r"], data["s_p"], data["d"]

        q = self.critic(s).gather(-1, a)
        q_p = self.targ_critic(s_p).max(dim=-1, keepdim=True).values
        y = r + 0.99 * q_p * (1 - d)

        loss = th.mean(((q - y.detach()) ** 2))
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        self.update_count += 1
        if self.update_count % 1_000 == 0:
            self.targ_critic.load_state_dict(self.critic.state_dict())

        return {}

    def step(self, state):
        if np.random.rand() > self.eps:
            th_state = th.from_numpy(state).unsqueeze(0).float()
            action = self.critic(th_state).argmax().detach().numpy()
        else:
            action = self.env.action_space.sample()

        self.eps = max(self.min_eps, self.eps * self.ann_coeff)
        return action, {}

    def eval_step(self, state: np.ndarray):
        th_state = th.from_numpy(state).unsqueeze(0).float()
        action = self.critic(th_state).argmax().detach().numpy()
        return action


def main():
    env = gym.make("CartPole-v1")
    runner = crl.OffPolicyRunner(
        env=env,
        agent=DQN(env),
        rollout_len=4,
        batch_size=32,
    )
    runner.run(rollouts=50_000, eval_freq=1_250)


if __name__ == "__main__":
    main()
