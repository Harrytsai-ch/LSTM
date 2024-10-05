# -*- coding: utf-8 -*-
"""「BiLSTM_QPC_pytorch_main.ipynb」的副本

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1gHZoULdp31Qozcu0xzHsd5VSyM888DD8
"""

import datetime as dt
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler,StandardScaler
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader

if torch.cuda.is_available():
  device = torch.device("cuda")  # 使用預設的GPU設備
else:
  device = torch.device("cpu")


qpc = yf.download( "4722.tw",start="2012-01-01",end = "2022-12-31" )
df = np.concatenate([ qpc["Close"].values.reshape(-1,1), qpc["Open"].values.reshape(-1,1), qpc["High"].values.reshape(-1,1),qpc["Low"].values.reshape(-1,1) ], axis=1) # 合併資料


input_size = df.shape[1]   # 輸入幾種特徵，就要更改

seq_len = 22*12# win_size
mid = int( len(df)*0.7 ) #切點
end = int( len(df)*0.9 )

# split data
training_set = df[:mid, :]
val_set = df[mid:end, :]
testing_set = df[mid:, :]


# Data normalization
#sc = MinMaxScaler(feature_range = (-1, 1))
sc = StandardScaler()
training_set_scaled = sc.fit_transform(training_set) #內部參數改變(也就是訓練時)用fit.transform
val_set_scaled = sc.transform(val_set)
test_set_scaled = sc.transform(testing_set)


# 將時間步轉換成特徵向量
def generate_sequence(data, win_size, anchor):
    X = []
    y = []
    for i in range(win_size, len(data), anchor):
        X.append(data[i-win_size:i, :])
        y.append(data[i,0])
    X = np.array(X)
    y = np.array(y)
    return torch.tensor(X).to(device) ,torch.tensor(y).to(device)

step = 1
X_train, y_train = generate_sequence(training_set_scaled, seq_len, step) #-->( predicted_time_points , seq_len , input_size(feature_num) )
X_val, y_val = generate_sequence(val_set_scaled, seq_len, step)
X_test,_ = generate_sequence(test_set_scaled, seq_len, step)


# Create dataloaders
train_dataset = TensorDataset(X_train, y_train)
val_dataset = TensorDataset(X_val, y_val)
train_dataloader = DataLoader(train_dataset, batch_size=256, shuffle=True) # 目標--->(batch_size, seq_len, input_size)
val_dataloader = DataLoader(val_dataset, batch_size=256, shuffle=True)
# 共有len(train_dataloader)144組批次數量，每個批次內部有16組時間序列，每組序列內部又有seq_len個時間步，每個時間步裡面有input_size個特徵向量

class BiLSTM(nn.Module):
    def __init__(self, input_size, hidden_sizes, output_size, bi):
        super().__init__()
        self.input_size = input_size
        self.output_size = output_size
        self.hidden_sizes = hidden_sizes
        self.num_layers =  len(hidden_sizes)
        self.LSTM_layers = nn.ModuleList()
        self.bi = bi
        #self.relu = nn.ReLU()
        if self.bi == 0:
          self.bi = 1
          bidirectional = False
        else:
          self.bi = 2
          bidirectional = True

        for i in range(self.num_layers):
            hidden_size = hidden_sizes[i]
            self.LSTM_layers.append(nn.LSTM(input_size, hidden_size, batch_first=True, bidirectional = bidirectional))
            input_size = hidden_size * self.bi  # 更新下一层的输入特征大小

        self.fc = nn.Linear(hidden_sizes[-1] * self.bi, output_size)  #最後一層隱藏結點數*2

    def forward(self, X):
        for i in range(self.num_layers):
            h0 = torch.rand( self.bi, X.size(0), self.hidden_sizes[i]).to(X.device) #(2_layer_unit, batch_size, hidden_size)
            c0 = torch.rand( self.bi, X.size(0), self.hidden_sizes[i]).to(X.device)
            X, _ = self.LSTM_layers[i](X, (h0, c0))

        out = self.fc(X[:, -1, :])

        return out

# In[]
num_epochs = 500
hidden_size = [8,16,32] # 節點數
output_size = input_size #輸出N個
learning_rate = 0.3#用adam就別調學習率
weight_decay = 0.0# L2


model = BiLSTM( input_size , hidden_size, output_size, 0 ).to(device)#  win_zize(外框) = seq_length(資料面的內容) 一個序列有多少時間步
optimizer = optim.Adam( model.parameters(), weight_decay = weight_decay ) #正則化 weight_decay lr = learning_rate
criterion = nn.MSELoss()


train_loss_list = []
val_loss_list = []
for epoch in range(num_epochs):
    model.train()
    train_loss = 0.0
    for i,(inputs, targets) in enumerate(train_dataloader):
        inputs ,targets = inputs.float() , targets.float()
        optimizer.zero_grad() #梯度歸零
        outputs = model(inputs) # inputs --->(batch_size, seq_len, input_size)
        loss = criterion(outputs[:,0], targets) # outputs---->(batch_size,feature_num)
        past_predictions = outputs.detach() #(batch_size,1)
        train_loss = loss.item() + train_loss
        loss.backward() #反向傳播
        optimizer.step() #梯度更新


    train_loss = train_loss / len(train_dataloader)
    train_loss_list.append(train_loss) # 每個epoch最後的結果會存放到list


    model.eval()
    with torch.no_grad():
        val_loss = 0.0
        for i, (inputs, targets) in enumerate(val_dataloader):
            inputs , targets = inputs.float() , targets.float()
            outputs = model(inputs)
            loss = criterion(outputs[:,0],targets)
            val_loss = val_loss + loss.item()
        val_loss =  val_loss / len(val_dataloader)
        val_loss_list.append(val_loss)


plt.plot(train_loss_list)
plt.plot(val_loss_list) #要改
plt.legend(['train_loss','val_loss'])
plt.grid()
plt.show()

train_loss_list[-5:],val_loss_list[-5:]

# In[]
# Step : Make Predictions
X_test = X_test.float() #( predicted_time_points , seq_len , input_size(feature_num) )
predicted_stock_price_tensor = model(X_test)
predicted_stock_price = predicted_stock_price_tensor.cpu().detach().numpy() #tensor--->numpy
predicted_stock_price = sc.inverse_transform(predicted_stock_price)


plt.plot(predicted_stock_price[:,0])
plt.plot(testing_set[seq_len:,0])
plt.legend(['predict','label'])
plt.grid()
plt.show()