import json
import os
import logging
import torch
from pathlib import Path

def ensure_parent_dir(path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)

def save_torch(path: str, tensor: torch.Tensor):
    ensure_parent_dir(path)
    torch.save(tensor.detach().cpu(), path)
    print(f"[cache] saved: {path}")


def load_torch(path: str, device: str):
    print(f"[cache] loading: {path} -> {device}")
    t = torch.load(path, map_location=device)
    return t.to(device)


def save_json(path: str, obj):
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"[cache] saved: {path}")


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def remove_module_from_state_dict(state_dict):
    new_state_dict = {}
    for key, value in state_dict.items():
        if key.startswith("module."):
            new_key = key[7:]
            new_state_dict[new_key] = value
        else:
            new_state_dict[key] = value
    return new_state_dict

def save_model(model, tokenizer, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    model_state_dict = model.state_dict()
    model_state_dict = remove_module_from_state_dict(model_state_dict)
    torch.save(model_state_dict, os.path.join(output_dir, "pytorch_model.bin"))
    model.config.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

def get_logger(name=None, log_level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(log_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
