import sys, math, random, time, datetime
import _pickle as pickle

import numpy as np
import pandas as pd

import mxnet as mx
from mxnet import autograd, gluon, nd, gpu
from mxnet.gluon import nn,rnn

from tqdm import trange

from nnHelper import smape,rmsle,ND,NRMSE,rho_risk,rho_risk2
from nnModels import QuantileLoss


### check point: save the temporal model params
def save_checkpoint(net, mark, valid_metric, save_path):
    if not path.exists(save_path):
        os.makedirs(save_path)
    filename = path.join(save_path, "mark_{:s}_metrics_{:.3f}".format(mark, valid_metric))
    filename +='.param'
    net.save_params(filename)

def DLPred(net, dt):
    if(dt.shape[0]<=60000):
        print(type(net(conv_dt, dt)))
        return net(dt)
    block_size = dt.shape[0] //60000+1
    pred_result = net(dt[0:60000,])
    for i in range(1,block_size):
        i = i*60000
        j = min(i+60000, dt.shape[0])
        block_pred = net(dt[i:j, ])
        pred_result = nd.concat(pred_result, block_pred, dim=0)
    return pred_result


"""
The main training process
"""
def DLPred2(net,conv_dt ,dt):
    if(dt.shape[0]<=60000):
        return net(conv_dt, dt)
    block_size = dt.shape[0] //60000+1
    pred_result = net(conv_dt[0:60000,], dt[0:60000,])
    for i in range(1,block_size):
        i = i*60000
        j = min(i+60000, dt.shape[0])
        block_pred = net(conv_dt[i:j, ], dt[i:j, ])
        pred_result = nd.concat(pred_result, block_pred, dim=0)
    #print('sss')
    return pred_result


"""
The main training process
"""
def nn_trainer(train_mark, model, train_data, test_conv_X, test_data_X,test_data_Y, trainer_params_list, ctx):
    """Parsing the params list"""
    ### The data
    batch_size = trainer_params_list['batch_size']
    epoches = trainer_params_list['epoch_num']

    loss_func = trainer_params_list['loss_func']
    initializer = trainer_params_list['initializer']
    optimizer = trainer_params_list['optimizer']
    optimizer_params = trainer_params_list['optimizer_params']

    #train_iter = gluon.data.DataLoader(train_data, batch_size, shuffle=True)
    ### The model
    mx.random.seed(123456)
    model.collect_params().initialize(initializer, ctx=ctx)
    trainer = gluon.Trainer(model.collect_params(),optimizer=optimizer, optimizer_params=optimizer_params)
    n_train = len(train_data)
    n_test = len(test_data_Y)
    ### The quantile loss
    ### The training process
    for epoch in trange(epoches):
        start=time.time()
        train_loss = 0
        k = 0
        train_iter = gluon.data.DataLoader(train_data, batch_size, shuffle=True)
        for conv_data, data, label in train_iter:
            label = label.as_in_context(ctx)
            with autograd.record():
                output = model(conv_data,data)
                loss = loss_func(output, label)
            loss.backward()
            trainer.step(batch_size,ignore_stale_grad=True)
            train_loss += nd.sum(loss).asscalar()
            k += 1
            if k*batch_size>200000: 
                print('training_data_nb:',k*batch_size)
                break
        ### The test loss
        ## The valid_true
        valid_true = test_data_Y.asnumpy()
        valid_pred = DLPred2(model,test_conv_X, test_data_X).asnumpy()
        valid_pred = valid_pred.reshape(valid_true.shape)
        print(valid_true.shape)
        print(valid_true[0,:])
        print(valid_pred[0,:])
        #valid_pred = valid_pred.reshape(-1,)
        #valid_true = valid_true.reshape(-1,)
        valid_pred2 = valid_pred[valid_true>0]
        valid_true2 = valid_true[valid_true>0]
         
        
        valid_loss = nd.sum(loss_func(nd.array(valid_true), nd.array(valid_pred))).asscalar()
        valid_ND = ND(valid_pred, valid_true);  valid_ND2 = ND(valid_pred2, valid_true2)
        valid_NRMSE = NRMSE(valid_pred, valid_true); valid_NRMSE2 = NRMSE(valid_pred2, valid_true2)
        print("Epoch %d, valid loss: %f valid ND: %f, valid NRMSE %f" % (epoch, valid_loss, valid_ND,valid_NRMSE))
        print("Epoch %d, valid loss: %f valid ND: %f, valid NRMSE %f" % (epoch, valid_loss, valid_ND2,valid_NRMSE2))
