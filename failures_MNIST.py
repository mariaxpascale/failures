from __future__ import print_function
import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms
from matplotlib import pyplot as plt
import functools
import sys
import os
import numpy as np
import pickle

from networks import LinearWeightDropout
from networks import LinearNet2L, LinearNet3L
from networks import ClassifierNet2L, ClassifierNet3L
from training_utils import train_classifier as train
from training_utils import test_classifier as test

from stats_utils import run_statistics, load_statistics

if __name__ == "__main__":

    training = True
    analysis = False
    plotting = False

    # ==================================================
    #   SETUP PARAMETERS

    # get parameters as inputs
    scaling = sys.argv[1]       # init pars scaling ("lin"=1/N or "sqrt"=1/sqrt(N))
    N = int(sys.argv[2])        # number of input and hidden units
    drop_p = float(sys.argv[3]) # probability of weight drop
    if not drop_p:
        drop_l = None
    else:
        drop_l = sys.argv[4]        # layer(s) with dropout, combined in a string ("1", "12", "13" etc)

    d_output = 10 # 10 digits in MNIST
    n_layers = 2

    if n_layers == 2:
        Net = ClassifierNet2L
        # Net = LinearNet2L
    elif n_layers == 3:
        Net = ClassifierNet3L
        # Net = LinearNet3L
    else:
        raise ValueError(f"Invalid number of layers, {n_layers}")

    # set (and create) output directory
    out_dir = f"outputs_MNIST/{n_layers}L_relu/"
    out_dir += f"{scaling}/"
    out_dir += f"N_{N:04d}/"
    out_dir += f"{drop_l}/"
    out_dir += f"q_{drop_p:.2f}"    
    os.makedirs(out_dir, exist_ok=True)

    print(f"Output directory:\n\t{out_dir}\n")

    # find device
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print(f"device = {device}")

    # ==================================================
    #   SETUP TRAINING

    n_epochs = 1000
    n_skip = min(1, n_epochs//100) # epochs to skip when saving data

    lr = 1e-4
    wd = 0.

    train_kwargs = {'batch_size': 100}
    test_kwargs = {'batch_size': 100}
    use_cuda = True
    cuda_kwargs = {'num_workers': 1,
                    'pin_memory': True,
                    'shuffle': True}
    train_kwargs.update(cuda_kwargs)
    test_kwargs.update(cuda_kwargs)


    # ==================================================
    #   TRAINING/TESTING

    if training:

        print("\nTRAINING ...")

        transform=transforms.Compose([
                transforms.ToTensor(),
                transforms.Lambda(lambda x: torch.flatten(x))
                ])
        train_dataset = datasets.MNIST('data', train=True, #download=True,
                            transform=transform)
        test_dataset = datasets.MNIST('data', train=False,
                            transform=transform)
        train_loader = torch.utils.data.DataLoader(train_dataset,**train_kwargs)
        test_loader = torch.utils.data.DataLoader(test_dataset, **test_kwargs)

        model = Net(d_input=28*28, d_output=10, d_hidden=N, layer_type=functools.partial(LinearWeightDropout, drop_p=drop_p), 
                    bias=False, scaling=scaling, drop_l=drop_l).to(device)
        optimizer = optim.SGD(model.parameters(), lr=lr, weight_decay=wd)

        model.save(f"{out_dir}/model_init")
        print(model)

        train_loss = []; train_acc = []
        test_loss = []; test_acc = []
        hidden = [np.array([]) for _ in range(n_layers - 1)]
        model_weights = [np.array([]) for _ in range(n_layers)]
        saved_epochs = []

        for epoch in range(n_epochs + 1):
            # train (except on the first epoch)
            train_loss_, train_acc_ = train(model, device, train_loader, optimizer, epoch, log_interval=1000)
            # test
            test_loss_, test_acc_, model_weights_, hidden_ = test(model, device, test_loader)

            train_loss.append(train_loss_); train_acc.append(train_acc_)
            test_loss.append(test_loss_); test_acc.append(test_acc_)
            # collect statistics
            if epoch % n_skip == 0:
                model.save(f"{out_dir}/model_trained")
                
                saved_epochs.append(epoch)
                np.save(f"{out_dir}/saved_epochs.npy", np.array(saved_epochs))
                np.save(f"{out_dir}/train_loss.npy", np.array(train_loss))
                np.save(f"{out_dir}/test_loss.npy", np.array(test_acc))
                
                for l in range(n_layers - 1):
                    hidden[l] = np.vstack((hidden[l], hidden_[l]))
                    np.save( f"{out_dir}/hidden_{l+1}.npy", hidden[l] )
                for l in range(n_layers):
                    model_weights[l] = np.vstack((model_weights[l], model_weights_[l]))
                    np.save( f"{out_dir}/weights_{l+1}.npy", model_weights[l] )

    # ==================================================
    #      ANALYSIS

    if analysis:

        print("STATISTICS ...")
        
        run_statistics(out_dir)


    # ==================================================
    #      PLOTS
    
    if plotting:
        print("PLOTTING ...")

        # re-load saved data
        saved_epochs = np.load(f"{out_dir}/saved_epochs.npy")
        train_loss = np.load(f"{out_dir}/train_loss.npy")
        test_acc = np.load(f"{out_dir}/test_loss.npy")
        with open(f"{out_dir}/hidden.pkl", "rb") as f:
            hidden = pickle.load(f)
        with open(f"{out_dir}/weights_norm.pkl", "rb") as f:
            weights_norm = pickle.load(f)
        with open(f"{out_dir}/SVDw.pkl", "rb") as f:
            Uw, Sw, Vw = pickle.load(f)
        with open(f"{out_dir}/SVD1.pkl", "rb") as f:
            U1, S1, V1 = pickle.load(f)
        with open(f"{out_dir}/SVD2.pkl", "rb") as f:
            U2, S2, V2 = pickle.load(f)
        with open(f"{out_dir}/SVD3.pkl", "rb") as f:
            U3, S3, V3 = pickle.load(f)

        PR = np.load(f"{out_dir}/PR.npy")

        title = f"init {'1/N' if scaling == 'lin' else '1/sqrt(N)'}; N ={N:04d}; drop {drop_l} wp {drop_p:.2f}"
        colors = ['C0', 'C1', 'C2', 'C3']

        # ALIGNMENT
        V2U1 = np.einsum('...ij,...jk->...ik', V2, U1)
        V3U2 = np.einsum('...ij,...jk->...ik', V3, U2)
        U3Uw = np.einsum('...ij,...jk->...ik', U3, Uw.T)
        V1Vw = np.einsum('...ij,...jk->...ik', V1, Vw.T)
        kwargs=dict(cmap="bwr", vmin=-1, vmax=1, aspect='equal')
        fig, axs_ = plt.subplots(1, 3, figsize=(12, 4))
        axs = axs_.ravel()
        # plt.subplots_adjust(wspace=0.4)
        plt.subplots_adjust(hspace=0.3)
        def plot_frame (frame):
            plt.cla()
            fig.suptitle(title+f" -- epoch {frame*n_skip}")
            ax = axs[0]
            ax.set_title(r"$V^n_3\cdot U^m_2$")
            ax.set_xlabel(r"$m$")
            ax.set_ylabel(r"$n$")
            im = ax.imshow(V3U2[frame, :d_output+2, :d_output+2], **kwargs)#; plt.colorbar(im, ax=ax)
            ax = axs[1]
            ax.set_title(r"$V^n_2\cdot U^m_1$")
            ax.set_xlabel(r"$m$")
            ax.set_ylabel(r"$n$")
            im = ax.imshow(V2U1[frame, :d_output+2, :d_output+2], **kwargs)#; plt.colorbar(im, ax=ax)
            ax = axs[2]
            ax.set_title(r"$V^n_1\cdot \tilde{V}^m$")
            ax.set_xlabel(r"$m$")
            ax.set_ylabel(r"$n$")
            im = ax.imshow(V1Vw[frame, :d_output+2, :d_output+2], **kwargs)#; plt.colorbar(im, ax=ax)
            # ax = axs[3]
            # ax.set_title(r"$U^n_3\cdot \tilde{U}^m$")
            # ax.set_xlabel("frame")
            # ax.set_ylabel(r"$n$")
            # ax.set_xticks(np.arange(3))
            # ax.set_yticks(np.arange(3))
            # im = ax.plot(U3Uw[:frame, 0])#; plt.colorbar(im, ax=ax)
        plot_frame(len(saved_epochs)-1)
        fig.savefig(f'{out_dir}/alignment.png', bbox_inches="tight")
        from matplotlib.animation import FuncAnimation
        duration=6
        frames=range(20)
        dt = duration*1000./20.
        ani = FuncAnimation(fig, plot_frame,
                            interval=dt,
                            frames=frames,
                            blit=False)
        ani.save(f'{out_dir}/alignment.gif')

        fig, axs_ = plt.subplots(1, 3, figsize=(14, 4))
        axs = axs_.ravel()
        # plt.subplots_adjust(wspace=0.4)
        plt.subplots_adjust(hspace=0.3)
        fig.suptitle(title)
        ax = axs[0]
        ax.set_ylim([0,1.1])
        ax.set_xlabel("epoch")
        ax.set_ylabel(r"$|V^n_3\cdot U^m_2|$")
        dims = V3U2.shape
        for i in range(d_output+1): # range(dims[1]):
            for j in range(d_output+1): #range(dims[2]):
                c = "C0" if i == j else "C1"
                ax.plot(saved_epochs, np.abs(V3U2[:, i, j]), c=c)
        ax = axs[1]
        ax.set_ylim([0,1.1])
        ax.set_xlabel("epoch")
        ax.set_ylabel(r"$|V^n_2\cdot U^m_1|$")
        dims = V2U1.shape
        for i in range(d_output+1): # range(dims[1]):
            for j in range(d_output+1): #range(dims[2]):
                c = "C0" if i == j else "C1"
                ax.plot(saved_epochs, np.abs(V2U1[:, i, j]), c=c)
        ax = axs[2]
        ax.set_ylim([0,1.1])
        ax.set_xlabel("epoch")
        ax.set_ylabel(r"$|V^n_1\cdot \tilde{V}^m|$")
        dims = V1Vw.shape
        for i in range(d_output+1): # range(dims[1]):
            for j in range(d_output+1): #range(dims[2]):
                c = "C0" if i == j else "C1"
                ax.plot(saved_epochs, np.abs(V1Vw[:, i, j]), c=c)
        fig.savefig(f'{out_dir}/alignment_vs_epoch.png', bbox_inches="tight")

        # PARTICIPATION RATIO AND LARGEST SINGULAR VALUE
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.set_title(title)
        ax.set_xlabel('epoch')
        ax.set_ylabel(r'singular values $W_1$', c='C0')
        ax.grid()
        ln10 = ax.plot(saved_epochs, S1[:,0], c='C0', label=r"$S^1_1$")
        ln11 = ax.plot(saved_epochs, S1[:,1], c='C0', ls="--", label=r"$S_1^2$")
        ln12 = ax.plot(saved_epochs, S1[:,2], c='C0', ls=":", label=r"$S_1^3$")
        ax1 = ax.twinx()
        ln20 = ax1.plot(saved_epochs, S2[:,0], c='C1', label=r"$S_2^1$")
        ln21 = ax1.plot(saved_epochs, S2[:,1], c='C1', ls="--", label=r"$S_2^2$")
        # lnPR = ax1.plot(saved_epochs, PR, c='C1', label="PR")
        ax1.set_ylabel(r'singular values $W_2$', c='C1')
        lns = ln10+ln11+ln12+ln20+ln21
        labs = [l.get_label() for l in lns]
        ax.legend(lns, labs, loc="right")
        fig.savefig(f'{out_dir}/plot_eval_PR.png', bbox_inches="tight")
        plt.close(fig)

        # ALL SINGULAR VALUES
        fig, axs = plt.subplots(1, 2, figsize=(9, 4))
        fig.suptitle(title)
        ax = axs[0]
        ax.set_title(r"$W_1$")
        ax.set_xlabel('epoch')
        ax.set_ylabel('singular value')
        for s in S1.T:
            ax.plot(saved_epochs, s)
        ax = axs[1]
        ax.set_title(r"$W_2$")
        ax.set_xlabel('epoch')
        ax.set_ylabel('singular value')
        for s in S2.T:
            ax.plot(saved_epochs, s)
        fig.savefig(f'{out_dir}/plot_s-values.png', bbox_inches="tight")
        plt.close(fig)

        # # BIMODALITY
        # fig, ax = plt.subplots(figsize=(6, 4))
        # ax.set_title(title)
        # ax.set_xlabel(r'$W^{(2)}_j$')
        # ax.set_ylabel(r'$(W^{(1)}\cdot w^*)_j$')
        # ax.scatter(W2[-1], np.sum(W1[-1]*w_star[None,:], axis=1), alpha=0.5, s=.1)
        # fig.savefig(f'{out_dir}/plot_scatter_W.png', bbox_inches="tight")
        # plt.close(fig)

        # # COS OF ANGLE BETWEEN PRINCIPAL COMPOMENTS AND WEIGHTS
        # # (check low rank of W)
        # fig, ax = plt.subplots(figsize=(6, 4))
        # ax.set_title(title)
        # ax.set_xlabel('epoch')
        # ax.set_ylim([0,1.1])
        # ax.grid()
        # # ax.set_xscale('log')
        # ax.set_ylabel(r'$|\cos\theta(u,v)|$')
        # ax.plot(saved_epochs, np.abs(V1_dot_wst), c='C0', label=r'$w^*, v_1$')
        # ax.plot(saved_epochs, np.abs(V2_dot_wst), c='C0', label=r'$w^*, v_2$', ls="--")
        # ax.plot(saved_epochs, np.abs(U1_dot_w2), c='C1', label=r'$w_2, u_1$')
        # ax.plot(saved_epochs, np.abs(U2_dot_w2), c='C1', label=r'$w_2, u_2$', ls="--")
        # ax.legend(loc="upper right", title=r"$u, v$")
        # fig.savefig(f'{out_dir}/plot_evec_theta.png', bbox_inches="tight")
        # plt.close(fig)

        # SINGULAR VALUES DISTRIBUTION
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.set_title(title)
        ax.set_xlabel('singular value')
        ax.set_ylabel('density')
        ax.hist(S1[0], density=True, bins=30, label="initial", alpha=0.3)
        ax.hist(S1[-1], density=True, bins=30, label="trained", alpha=0.3)
        ax.legend(loc="best")
        fig.savefig(f'{out_dir}/plot_eval_distr.png', bbox_inches="tight")
        plt.close(fig)

        # TRAIN AND TEST LOSS
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.scatter(np.arange(len(test_acc)), test_acc, label="test", s=2, c="C1")
        ax.plot(train_loss, label="train", c="C0")
        ax.set_title(title)
        ax.grid()
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_ylabel('Train and test loss')
        ax.set_xlabel('epoch')
        ax.legend(loc="best")
        fig.savefig(f'{out_dir}/plot_loss.png', bbox_inches="tight")
        plt.close(fig)

        # NORM OF THE WEIGHTS
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.set_title(title)
        ax.set_ylabel('L2 weight norm')
        ax.grid()
        # ax.set_xscale('log')
        ax.set_xlabel('epoch')
        ax.set_ylim([0,1])
        for i, (norm, c) in enumerate(zip(weights_norm, colors)):
            ax.plot(saved_epochs, norm/norm[0], c=c, label=f'{i+1}: {norm[0]:.2f}')
        ax.legend(loc='best', title="layer: init value")
        fig.savefig(f'{out_dir}/plot_weights_norm.png', bbox_inches="tight")
        plt.close(fig)

        # HISTOGRAM OF THE WEIGHTS
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.set_title(title)
        ax.set_xlabel('L2 weight norm (trained)')
        ax.set_ylabel('density')
        ax.set_xlim([-1/np.sqrt(N),1/np.sqrt(N)])
        ax.hist(W1[-1].ravel(), density=True, bins=100, label="W1", alpha=0.3)
        ax.hist(W2[-1].ravel(), density=True, bins=100, label="W2", alpha=0.3)
        ax.legend(loc="best")
        fig.savefig(f'{out_dir}/plot_weights_histogram.png', bbox_inches="tight")
        plt.close(fig)

        # VARIANCE OF THE HIDDEN LAYER
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.set_title(title)
        ax.set_ylabel('Hidden layer variance')
        ax.set_xlabel('epoch')
        ax.grid()
        ax.plot(saved_epochs, np.linalg.norm(hidden, axis=1))
        fig.savefig(f'{out_dir}/plot_hidden_layer_variance.png', bbox_inches="tight")
        plt.close(fig)

        # HISTOGRAM OF THE HIDDEN LAYER
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.set_title(title)
        ax.set_xlabel('Hidden layer activity')
        ax.set_ylabel('density')
        ax.hist(hidden[-1,0], density=True, bins="sqrt", label="initial", alpha=0.3)
        ax.hist(hidden[-1,1], density=True, bins="sqrt", label="trained", alpha=0.3)
        ax.legend(loc="best")
        fig.savefig(f'{out_dir}/plot_hidden_layer_histogram.png', bbox_inches="tight")
        plt.close(fig)

