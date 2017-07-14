#!/usr/bin/env python

import argparse
import json
import grasp_env
import numpy as np
import random
import sys
import util as u

# kuka joints
# 0 - kuka joints j0
# ...
# 6 - kuka join j6, end effector rotation
# 7 - also (?) end effector rotation
# 8 - right finger upper; 0 to shut, -0.2 to open
# 9 - ?
# 10 - right finger lower; +0.1 to shut, -0.2 to open
# 11 - left finger upper; 0 to shut, +0.2 to open
# 12 - ?
# 13 - left finger lower; -0.1 to shut, -0.2 to open


class RandomAgent(object):
  def __init__(self, _env, log_directory):
    self.log = u.Log(log_directory)

  def rollout(self, env, episode):
    state = env.reset()
    step = 0
    done = False
    while not done:
      action = env.action_space.sample()
      state, reward, done, info = env.step(action)
      self.log.append(episode, step, state, action, reward, info)
      step += 1

class GreedyAgent(object):
  def __init__(self, env, log_directory):
    self.a_idx = 0  # which action idx last changed
    self.actions = np.zeros(7)
    self.log = u.Log(log_directory)

  def pick_new_random_action(self):
    self.actions[self.a_idx] = 0
    self.a_idx = random.randrange(0, 7)
    self.actions[self.a_idx] = -1 if random.random() <= 0.5 else 1

  def rollout(self, env, episode):
    env.reset()
    # do nothing once just to bootstrap value for "best distance"
    # note: reward is -1 / 1 and we ignore it and pull distance from info
    _state, _reward, done, info = env.step(np.zeros(7))
    # TODO: cornerish case of already being "done" at reset....
    best_distance = info['distance']
    # pick a random action idx to start with
    self.pick_new_random_action()

    step = 0
    while True:
      # try action
      state, reward, done, info = env.step(self.actions)
      self.log.append(episode, step, state, self.actions, reward, info)
      if done: return
      step += 1

      distance = info['distance']
      if distance < best_distance - 1e-3:
        # if distance is better than best_distance we keep this action
        # ( add margin of 1e-2 since joint limits may mean we make
        # very small progress but are effectively stuck )
        best_distance = distance
      else:
        # rollback latest step by taking a step back in opposite
        # direction before deciding new action for next time
        self.actions[self.a_idx] *= -1
        state, reward, done, info = env.step(self.actions)
        self.log.append(episode, step, state, self.actions, reward, info)

        # sanity check reversing actually _did_ get us back to best
        distance = info['distance']
        assert np.isclose(distance, best_distance, atol=0.1)
        self.log.append(episode, step, state, self.actions, reward, info)
        if done: return
        step += 1
        # try something else next time
        self.pick_new_random_action()


if __name__ == "__main__":
  parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('--agent', type=str, default="random", help="agent to run")
  parser.add_argument('--gui', action='store_true')
  parser.add_argument('--max_steps', type=int, default=50, help="env max steps")
  parser.add_argument('--num_episodes', type=int, default=100, help="number of rollouts to do")
  parser.add_argument('--run', type=str, default=None, help="base directory for image output")
  opts = parser.parse_args()
  assert opts.run is not None
  print >>sys.stderr, "OPTS", opts

  env = grasp_env.GraspEnv(gui=opts.gui, max_steps=opts.max_steps)

  if opts.agent == "random":
    agent = RandomAgent(env, opts.run)
  elif opts.agent == "greedy":
    agent = GreedyAgent(env, opts.run)
  else:
    raise Exception("unknown agent type [%s]" % opts.agent)

  for episode in range(opts.num_episodes):
    agent.rollout(env, episode)
