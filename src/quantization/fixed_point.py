import numpy as np
import torch
import torch.nn as nn
from sendWeights import get_trained_model
from einops import rearrange, repeat
from FixedPointViT import FixedPointViT
import matplotlib.pyplot as plt
from few_shot.prototypical_loss import get_prototypes, prototypical_evaluation, prototypical_evaluation_per_patient
from sklearn.metrics import roc_auc_score, confusion_matrix, accuracy_score, f1_score
import time
from tqdm import tqdm
from few_shot_train import get_support_set_per_patient, init_seed
from dataset import get_data_loader_siena
from utils.parser_util import get_parser


options = get_parser().parse_args()
init_seed(options)
device = 'cuda:0' if torch.cuda.is_available() and options.cuda else 'cpu'

CLIP_VAL = 1
FRACTION_BITS = 6
total_weights = torch.zeros(0).to(device)


def make_fxp(source_weight):
    global total_weights

    target_weight = torch.where(source_weight > CLIP_VAL, CLIP_VAL, source_weight)
    target_weight = torch.where(target_weight < -CLIP_VAL,  -CLIP_VAL, target_weight)
    target_weight *= (2**FRACTION_BITS)
    target_weight = target_weight.to(torch.int)
    total_weights = torch.cat((total_weights, target_weight.flatten()))
    return target_weight.to(torch.float) / (2**FRACTION_BITS)


def send_weights(source_model, target_model):
    target_model.pos_embedding.data = make_fxp(source_model.pos_embedding)
    target_model.cls_token.data = make_fxp(source_model.cls_token)
    target_model.mlp_head[0].weight.data = make_fxp(source_model.mlp_head[0].weight)
    target_model.mlp_head[0].bias.data = make_fxp(source_model.mlp_head[0].bias)

    target_model.mlp_head[1].weight.data = make_fxp(source_model.mlp_head[1].weight)
    target_model.mlp_head[1].bias.data = make_fxp(source_model.mlp_head[1].bias)

    target_model.to_patch_embedding[1].weight.data = make_fxp(source_model.to_patch_embedding[1].weight)
    target_model.to_patch_embedding[1].bias.data = make_fxp(source_model.to_patch_embedding[1].bias)

    target_model.to_patch_embedding[2].weight.data = make_fxp(source_model.to_patch_embedding[2].weight)
    target_model.to_patch_embedding[2].bias.data = make_fxp(source_model.to_patch_embedding[2].bias)

    target_model.to_patch_embedding[3].weight.data = make_fxp(source_model.to_patch_embedding[3].weight)
    target_model.to_patch_embedding[3].bias.data = make_fxp(source_model.to_patch_embedding[3].bias)

    for l in range(4):
        target_model.transformer.layers[l][0].norm.weight.data = make_fxp(
            source_model.transformer.layers[l][0].norm.weight)
        target_model.transformer.layers[l][0].norm.bias.data = make_fxp(source_model.transformer.layers[l][0].norm.bias)
        target_model.transformer.layers[l][0].fn.to_out[0].weight.data = make_fxp(
            source_model.transformer.layers[l][0].fn.to_out[0].weight)
        target_model.transformer.layers[l][0].fn.to_out[0].bias.data = make_fxp(
            source_model.transformer.layers[l][0].fn.to_out[0].bias)
        target_model.transformer.layers[l][1].norm.weight.data = make_fxp(
            source_model.transformer.layers[l][1].norm.weight)
        target_model.transformer.layers[l][1].norm.bias.data = make_fxp(source_model.transformer.layers[l][1].norm.bias)
        target_model.transformer.layers[l][1].fn.net[0].weight.data = make_fxp(
            source_model.transformer.layers[l][1].fn.net[0].weight)
        target_model.transformer.layers[l][1].fn.net[0].bias.data = make_fxp(
            source_model.transformer.layers[l][1].fn.net[0].bias)
        target_model.transformer.layers[l][1].fn.net[3].weight.data = make_fxp(
            source_model.transformer.layers[l][1].fn.net[3].weight)
        target_model.transformer.layers[l][1].fn.net[3].bias.data = make_fxp(
            source_model.transformer.layers[l][1].fn.net[3].bias)

        target_model.transformer.layers[l][0].fn.to_qkv.weight.data = make_fxp(
            source_model.transformer.layers[l][0].fn.to_qkv.weight)


def test(opt, test_dataloader, model, print_results=False, target_model = None):
    """
    Test the model trained with the prototypical learning algorithm
    """

    model.eval()

    x_support_set_all, y_support_set_all = get_support_set_per_patient(opt.num_support_val,
                                                               data_dir=opt.siena_data_dir,
                                                               patient_ids=opt.patients)
    prototypes_all = []

    for x_support_set, y_support_set in zip(x_support_set_all, y_support_set_all):
        x_support_set = torch.tensor(x_support_set).to(device)
        y_support_set = torch.tensor(y_support_set).to(device)

        x = x_support_set.reshape((x_support_set.shape[0], 1, -1, x_support_set.shape[3]))
        model_output = model(x)
        prototypes = get_prototypes(model_output, target=y_support_set)
        # print("Prototypes", prototypes)
        prototypes_all.append(prototypes)

    predict = []
    predict_prob = []
    true_label = []
    for batch in tqdm(test_dataloader):
        x, y = batch
        x, y = x.to(device), y.to(device)

        x = x.reshape((x.shape[0], 1, -1, x.shape[3]))

        model_output = model(x)

        prob, output = prototypical_evaluation_per_patient(prototypes_all, model_output)
        predict.append(output.detach().cpu().numpy())
        predict_prob.append(prob.detach().cpu().numpy())
        true_label.append(y.detach().cpu().numpy())
    predict = np.hstack(predict)
    predict_prob = np.hstack(predict_prob)
    true_label = np.hstack(true_label)

    # Placeholder for results
    results = {
        "seed": opt.manual_seed,
        "num_support": opt.num_support_val,
        "skip_base_learner": opt.skip_base_learner,
        "skip_finetune": opt.skip_finetune,
        "patients": opt.patients,
        "finetune_patients": opt.finetune_patients,
        "excluded_patients": opt.excluded_patients,
        "auc": roc_auc_score(true_label, predict_prob)
    }

    if print_results:
        print(results)





def main():
    model = get_trained_model()
    model.eval()
    l = 0
    net = FixedPointViT(image_size=(3200, 15), patch_size=(80, 5), num_classes=16, dim=16, depth=4, heads=4, mlp_dim=4,
                        pool='cls',
                        channels=1, dim_head=4, dropout=0.2, emb_dropout=0.2)
    net.eval()
    print(model)
    print(net)
    for name, param in model.named_parameters():
        if param.requires_grad:
            print(name)

    send_weights(model, net)

    all_patients = [0, 1, 3, 5, 6, 7, 9, 10, 11, 12, 13, 14, 16, 17]
    test_patient_ids = [p for p in all_patients if p not in options.excluded_patients]
    test_dataloader = get_data_loader_siena(batch_size=32, patient_ids=test_patient_ids,
                                            save_dir=options.siena_data_dir)
    train_dataloader = get_data_loader_siena(batch_size=32, patient_ids=options.patients,
                                             save_dir=options.siena_data_dir)

    # test(options, test_dataloader, model, print_results=True)
    test(options, test_dataloader, net, print_results=True)
    input_signal = next(iter(test_dataloader))[0].to(device)
    input_signal = input_signal.reshape((input_signal.shape[0], 1, -1, input_signal.shape[3]))

    error = torch.sum(torch.abs(net(input_signal) - model(input_signal)))
    print("Error", error)
    print(total_weights.shape)
    # Create a histogram
    plt.hist(total_weights.detach().cpu().numpy(), bins=20, color='blue', alpha=0.7)
    plt.xlabel('Value')
    plt.ylabel('Frequency')
    plt.title('Histogram of Total Weights')
    plt.grid(True)
    plt.show()


if __name__ == '__main__':
    main()