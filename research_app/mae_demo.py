import os
import urllib

import numpy as np
import requests
import torch
from PIL import Image

from fb_mae import models_mae

# define the utils

imagenet_mean = np.array([0.485, 0.456, 0.406])
imagenet_std = np.array([0.229, 0.224, 0.225])


def prepare_model(chkpt_dir, arch="mae_vit_large_patch16"):
    # build model
    model = getattr(models_mae, arch)()
    # load model
    checkpoint = torch.load(chkpt_dir, map_location="cpu")
    msg = model.load_state_dict(checkpoint["model"], strict=False)
    print(msg)
    return model


def show_image(image, title=""):
    # image is [H, W, 3]
    assert image.shape[2] == 3
    image = (
        torch.clip((image * imagenet_std + imagenet_mean) * 255, 0, 255).int().numpy()
    )
    image = Image.fromarray(image.astype("uint8"))
    return image


def run_one_image(img, model):
    x = torch.tensor(img)

    # make it a batch-like
    x = x.unsqueeze(dim=0)
    x = torch.einsum("nhwc->nchw", x)

    # run MAE
    loss, y, mask = model(x.float(), mask_ratio=0.75)
    y = model.unpatchify(y)
    y = torch.einsum("nchw->nhwc", y).detach().cpu()

    # visualize the mask
    mask = mask.detach()
    mask = mask.unsqueeze(-1).repeat(
        1, 1, model.patch_embed.patch_size[0] ** 2 * 3
    )  # (N, H*W, p*p*3)
    mask = model.unpatchify(mask)  # 1 is removing, 0 is keeping
    mask = torch.einsum("nchw->nhwc", mask).detach().cpu()

    x = torch.einsum("nchw->nhwc", x)

    # masked image
    im_masked = x * (1 - mask)

    # MAE reconstruction pasted with visible patches
    im_paste = x * (1 - mask) + y * mask

    # make the plt figure larger

    original_image = show_image(x[0], "original")

    masked_image = show_image(im_masked[0], "masked")

    recons_image = show_image(y[0], "reconstruction")

    visible_image = show_image(im_paste[0], "reconstruction + visible")

    return {
        "original": original_image,
        "masked": masked_image,
        "reconstructed": recons_image,
        "visible": visible_image,
    }


class Demo:
    def __init__(self):
        # This is an MAE model trained with pixels as targets for visualization (ViT-Large, training mask ratio=0.75)
        # download checkpoint if not exist
        if not os.path.exists("resources/mae_visualize_vit_large.pth"):
            urllib.request.urlretrieve(
                "https://dl.fbaipublicfiles.com/mae/visualize/mae_visualize_vit_large.pth",
                "resources/mae_visualize_vit_large.pth",
            )

        chkpt_dir = "resources/mae_visualize_vit_large.pth"
        self.model_mae = prepare_model(chkpt_dir, "mae_vit_large_patch16")
        print("Model loaded.")

    def predict(self, image: Image.Image):
        # load an image
        img = image.resize((224, 224))
        img = np.array(img) / 255.0

        assert img.shape == (224, 224, 3)

        # normalize by ImageNet mean and std
        img = img - imagenet_mean
        img = img / imagenet_std

        original_image = show_image(torch.tensor(img))

        # make random mask reproducible (comment out to make it change)
        torch.manual_seed(2)
        print("MAE with pixel reconstruction:")
        return run_one_image(img, self.model_mae)


if __name__ == "__main__":
    img_url = "https://user-images.githubusercontent.com/11435359/147738734-196fd92f-9260-48d5-ba7e-bf103d29364d.jpg"  # fox, from ILSVRC2012_val_00046145
    # img_url = 'https://user-images.githubusercontent.com/11435359/147743081-0428eecf-89e5-4e07-8da5-a30fd73cc0ba.jpg' # cucumber, from ILSVRC2012_val_00047851
    img = Image.open(requests.get(img_url, stream=True).raw)
    model = Demo()
    model.predict(img)
