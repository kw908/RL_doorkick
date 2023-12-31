import torch as T
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np

class DeepQNetwork(nn.Module):
    def __init__(self, lr, input_dims, fc1_dims, fc2_dims, n_actions):
        super(DeepQNetwork, self).__init__()
        self.input_dims = input_dims
        self.fc1_dims = fc1_dims #fc stands for fully connected layer, also known as "linear layer"
        self.fc2_dims = fc2_dims
        self.n_actions = n_actions
        self.fc1 = nn.Linear(*self.input_dims, self.fc1_dims) # aristerisk means any number of dimensions
        self.fc2 = nn.Linear(self.fc1_dims,self.fc2_dims)
        self.fc3 = nn.Linear(self.fc2_dims, self.n_actions)
        self.optimizer = optim.Adam(self.parameters(),lr=lr)
        self.loss = nn.MSELoss() # as in the DQN paper
        self.device = T.device('cuda:0' if T.cuda.is_available() else 'cpu')
        self.to(self.device)

    def forward(self, state): # the network
        x = F.relu(self.fc1(state))  
        x - F.relu(self.fc2(x))
        actions = self.fc3(x)

        return actions
    

class Agent():
    def __init__(self, gamma, epsilon, lr, input_dims, batch_size, n_actions,
                 max_mem_size=300000, eps_end=0.01, eps_dec=5e-4):
        self.gamma = gamma
        self.epsilon = epsilon
        self.eps_min = eps_end
        self.eps_dec = eps_dec
        self.lr = lr
        self.action_space = [i for i in range(n_actions)]
        self.mem_size = max_mem_size
        self.batch_size = batch_size
        self.meme_cntr = 0
        self.loss_memory_in_eps = []
        self.loss_memory = []

        self.Q_eval = DeepQNetwork(self.lr, n_actions=n_actions, 
                                   input_dims=input_dims, fc1_dims=256, fc2_dims=256)
        self.state_memory = np.zeros((self.mem_size, *input_dims), dtype=np.float32)
        self.new_state_memory = np.zeros((self.mem_size, *input_dims),dtype=np.float32)

        self.action_memory = np.zeros(self.mem_size, dtype=np.int32)
        self.reward_memory = np.zeros(self.mem_size, dtype=np.float32)
        self.terminal_memory = np.zeros(self.mem_size, dtype=np.bool_)

    def store_transition(self, state, action, reward, state_, done):
        # store the experience replay D
        # "state" is current state, "state_" is the next state
        index = self.meme_cntr 
        self.state_memory[index] = state
        self.new_state_memory[index] = state_
        self.reward_memory[index] = reward
        self.action_memory[index] = action
        self.terminal_memory[index] = done

        self.meme_cntr += 1

    def choose_action(self, observation):
        if np.random.random()>self.epsilon: #epsilon-greedy
            state = T.tensor([observation]).to(self.Q_eval.device)
            
            """Action is taken based on the updated value function (forward propagation throught nn),"""
            """but the policy is still epsilon-greedy (q-learning is off-policy learning)."""

            actions = self.Q_eval.forward(state)  
            action = T.argmax(actions).item()
        else:
            action = np.random.choice(self.action_space)

        return action
        
    def learn(self):
        if self.meme_cntr < self.batch_size: #start learning only when there is enough samples in the batch
            return
        
        self.Q_eval.optimizer.zero_grad()

        max_mem = min(self.meme_cntr, self.mem_size)
        batch = np.random.choice(max_mem, self.batch_size, replace=False)  # randomly sample a minibatch of size "batch_size", "batch" here means minibatch

        batch_index = np.arange(self.batch_size, dtype=np.int32)
        
        # Convert the batches to tensor
        state_batch = T.tensor(self.state_memory[batch]).to(self.Q_eval.device)
        new_state_batch = T.tensor(self.new_state_memory[batch]).to(self.Q_eval.device)
        reward_batch = T.tensor(self.reward_memory[batch]).to(self.Q_eval.device)
        terminal_batch = T.tensor(self.terminal_memory[batch]).to(self.Q_eval.device)

        """indexing with array is handy here because the minibatch is randomly picked from the whole batch"""

        action_batch = self.action_memory[batch]

        q_eval = self.Q_eval.forward(state_batch)[batch_index, action_batch] # q value of each action in the batch

        #output of Q_eval.forward is 64x4, q_eval is (64,)

        q_next = self.Q_eval.forward(new_state_batch) # why not [batch_index, action_batch] again
        q_next[terminal_batch] = 0.0

        q_target = reward_batch + self.gamma * T.max(q_next, dim=1)[0] # q_next is 64x4, dim=1 means taking the maximum along the action axis

        """tensor uses both positive and negative indices to index the dimensions of array, works the same way as ndarray indexing"""

        """doing gradient descent below"""

        loss = self.Q_eval.loss(q_target, q_eval).to(self.Q_eval.device)
        self.loss_memory_in_eps.append(np.mean(loss.detach().numpy()))
        loss.backward()
        self.Q_eval.optimizer.step()
        
        """decrease epsilon (the video did this)"""

        self.epsilon = self.epsilon - self.eps_dec if self.epsilon > self.eps_min \
                       else self.eps_min