"""
Metrics computation for negotiation simulation results.
"""
from transformers import logging
logging.set_verbosity_error()
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

MODEL_NAME = "gpt2"
_tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
_model = AutoModelForCausalLM.from_pretrained(MODEL_NAME).eval()
if torch.cuda.is_available():
    _model.to("cuda")

def compute_perplexity(text: str) -> float:
    encodings = _tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    input_ids = encodings.input_ids.to(_model.device)
    with torch.no_grad():
        outputs = _model(input_ids, labels=input_ids)
        # HuggingFace’s CausalLMOutputWithCrossAttentions includes .loss directly
        loss = outputs.loss
    return torch.exp(loss).item()