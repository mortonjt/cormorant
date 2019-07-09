import torch
from torch.utils.data import DataLoader

import logging
from datetime import datetime
from math import sqrt

from cormorant.models import Cormorant
from cormorant.tests import cormorant_tests

from cormorant.train import TrainCormorant
from cormorant.train import init_args, init_cuda, init_optimizer, init_scheduler
from cormorant.data.utils import initialize_datasets
from cormorant.cg_lib import global_cg_dict

from cormorant.data.collate import collate_fn

# This makes printing tensors more readable.
torch.set_printoptions(linewidth=1000, threshold=100000)

def main():

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger()

    # Initialize arguments
    args = init_args()

    # Initialize device and data type
    device, dtype = init_cuda(args)

    # Initializing CG coefficients
    global_cg_dict(maxl=max(args.maxl+args.max_sh), dtype=dtype, device=device)

    # Initialize dataloder
    datasets, num_species, charge_scale = initialize_datasets(args.datadir, args.dataset, subset=args.subset)

    # Construct PyTorch dataloaders from datasets
    dataloaders = {split: DataLoader(dataset, batch_size=args.batch_size, shuffle=args.shuffle, num_workers=0, collate_fn=collate_fn) for split, dataset in datasets.items()}

    # Initialize model
    model = Cormorant(args.num_cg_levels, args.maxl, args.max_sh, args.num_channels, num_species,
                        args.cutoff_type, args.hard_cut_rad, args.soft_cut_rad, args.soft_cut_width,
                        args.weight_init, args.level_gain, args.charge_power, args.basis_set,
                        charge_scale, args.gaussian_mask,
                        args.top, args.input, args.num_mpnn_levels,
                        device=device, dtype=dtype)

    # Initialize the scheduler and optimizer
    optimizer = init_optimizer(args, model)
    scheduler, restart_epochs = init_scheduler(args, optimizer)

    # Define a loss function. Just use L2 loss for now.
    loss_fn = torch.nn.functional.mse_loss

    # Apply the covariance and permutation invariance tests.
    cormorant_tests(model, datasets['train'], args, charge_scale=charge_scale)

    # Instantiate the training class
    trainer = TrainCormorant(args, dataloaders, model, loss_fn, optimizer, scheduler, restart_epochs, device, dtype)

    # Load from checkpoint file. If no checkpoint file exists, automatically does nothing.
    trainer.load_checkpoint()

    # Train model.
    trainer.train()

    # Test predictions on best model and also last checkpointed model.
    trainer.predict()

if __name__ == '__main__':
    main()