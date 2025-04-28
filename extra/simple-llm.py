import argparse
from fastapi import FastAPI
from pydantic import BaseModel
import torch
import sys


# Globals
model = None
tokenizer = None
backend = "transformers"
device = "cpu"
# Quick API server - don't know if it's robust
app = FastAPI()


class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 300
    temperature: float = 0.5


# Huggingface hub loading; can be slow
def load_transformers_model(model_name: str, device: str = "cpu"):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float32,
        device_map="auto" if device == "auto" else {"": device}
    )
    return tokenizer, model


# CTransformers loading; very simple models
def load_ctransformers_model(model_name: str):
    from ctransformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(model_name)
    return None, model  # No separate tokenizer needed


@app.post("/generate")
async def generate(req: GenerateRequest):
    error = None
    response = None
    reply = {}
    if backend == "transformers":
        try:
            inputs = tokenizer(req.prompt, return_tensors="pt").to(device)
            with torch.no_grad():
                outputs = model.generate(**inputs,
                                         max_new_tokens=req.max_tokens,
                                         temperature=req.temperature,
                                         do_sample=True)
                generated_text = tokenizer.decode(outputs[0],
                                                  skip_special_tokens=True)
                response = generated_text[len(req.prompt):].strip()
        except Exception as e:
            error = f"Unexpected error: {e}"
    elif backend == "ctransformers":
        try:
            response = model(req.prompt, max_new_tokens=req.max_tokens).strip()
        except Exception as e:
            error = f"Unexpected error: {e}"
    else:
        error = f"Unsupported backend: {backend}"

    if response:
        reply["response"] = response

    if error:
        reply["error"] = error

    return reply


if __name__ == "__main__":

    # Just use argparse here for a quick 'n dirty thing.  Not for production.
    parser = argparse.ArgumentParser(description="Simple LLM Server")
    parser.add_argument("--model", type=str, required=True,
                        help="Model name or path (/list dumps hugging faces)")
    parser.add_argument("--backend", type=str,
                        choices=["transformers", "ctransformers"],
                        default="transformers",
                        help="Backend to use: transformers or ctransformers")
    parser.add_argument("--device", type=str, default="cpu",
                        help="Device to run on: cpu, cuda, auto")
    parser.add_argument("--port", type=int, default=8000,
                        help="Port to serve the API on")
    args = parser.parse_args()

    backend = args.backend
    device = args.device
    model = args.model

    if model.startswith("/list"):
        model_args = model.split(" ")

        try:
            import huggingface_hub as HH
        except:
            raise RuntimeError("Missing `huggingface_hub` module.")

        if len(model_args) == 1:
            # no list details
            model_filter = None
        else:
            model_filter = " ".join(model_args[1:])

        models = HH.list_models(filter=model_filter, limit=100)
        for mod in models:
            print(f"{mod.modelId} - {mod.tags}")
        sys.exit(0)

    if backend == "transformers":
        tokenizer, model = load_transformers_model(args.model, device)
    elif backend == "ctransformers":
        tokenizer, model = load_ctransformers_model(args.model)
    else:
        raise ValueError("Unsupported backend.")

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=args.port)
