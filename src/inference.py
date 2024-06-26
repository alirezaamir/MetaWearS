import os
import sys
import math
import json
import warnings

# Filter out the specific UserWarning related to torchvision
warnings.filterwarnings("ignore", category=UserWarning, message="Failed to load image Python extension")
# TODO solve the CUDA version issue

os.environ['CUDA_VISIBLE_DEVICES'] = '0'
import random
import time
import torch
from torch import nn
from sklearn.metrics import roc_auc_score, accuracy_score, f1_score
import numpy as np
from scipy.signal import stft
from tqdm import tqdm
from einops import rearrange, repeat
from einops.layers.torch import Rearrange
from dataset import TUHDataset, get_data_loader_siena
import torch.multiprocessing
torch.multiprocessing.set_sharing_strategy('file_system')
from sklearn.metrics import confusion_matrix
from utils.utils import thresh_max_f1


def seed_everything(seed=99):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True


seed_everything(seed=99)


def test_sample_base():
    data_directory = '/home/amirshah/EPFL/EpilepsyTransformer/input/Siena/'
    test_loader = get_data_loader_siena(32, data_directory)

    test_label_all = []
    test_prob_all = np.zeros(0, dtype=np.float)

    with torch.no_grad():
        for data, label in tqdm(test_loader):
            test_label_all.extend(label.cpu().numpy())
            test_prob = model(data.to(device))

            test_prob = torch.squeeze(sigmoid(test_prob))
            test_prob_all = np.concatenate((test_prob_all, test_prob.cpu().numpy()))

    best_th = thresh_max_f1(test_label_all, test_prob_all)
    test_predict_all = np.where(test_prob_all > best_th, 1, 0)

    # Placeholder for results
    results = {
        "best_threshold": best_th,
        "accuracy": accuracy_score(test_label_all, test_predict_all),
        "f1_score": f1_score(test_label_all, test_predict_all),
        "auc": roc_auc_score(test_label_all, test_prob_all),
        "confusion_matrix": confusion_matrix(test_label_all, test_predict_all).tolist()
    }

    print(results)


sample_rate = 256
eeg_type = 'stft'  # 'original', 'bipolar', 'stft'
device = 'cuda:0'
# device = 'cpu'

# model = torch.load('inference_ck_0.9208', map_location=torch.device(device))
root_path = '/home/amirshah/EPFL/EpilepsyTransformer/TUSZv2/preprocess'
model_path = os.path.join(root_path, 'test_STFT/test_model_21_0.9274234153874015')

model = torch.load(model_path,  map_location=torch.device(device))
print(sum(p.numel() for p in model.parameters() if p.requires_grad))
model.eval()
sigmoid = nn.Sigmoid()

test_sample_base()