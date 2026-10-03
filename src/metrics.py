"""
Metrics computation for negotiation simulation results.

Same GPT-2 perplexity as v0 (whole transcript, truncated to 512 tokens).
The model now loads on first use instead of at import, so importing the
package does not need transformers or a download.
"""

MODEL_NAME = "gpt2"
_tokenizer = None
_model = None


def _load():
    global _tokenizer, _model
    if _model is None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from transformers import logging as hf_logging

        hf_logging.set_verbosity_error()
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForCausalLM.from_pretrained(MODEL_NAME).eval()
        if torch.cuda.is_available():
            _model.to("cuda")
    return _tokenizer, _model


def compute_perplexity(text: str) -> float:
    import torch

    tokenizer, model = _load()
    encodings = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    input_ids = encodings.input_ids.to(model.device)
    with torch.no_grad():
        outputs = model(input_ids, labels=input_ids)
        # HuggingFace's CausalLMOutputWithCrossAttentions includes .loss directly
        loss = outputs.loss
    return torch.exp(loss).item()
