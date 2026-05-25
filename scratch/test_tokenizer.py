import yaml
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

def test_tok():
    print("Loading tokenizer...")
    try:
        tok = AutoTokenizer.from_pretrained("kronos_module/models/kronos_tokenizer")
        print("Tokenizer loaded successfully!")
        
        sequence_text = "1.000000 2.000000 3.000000 4.000000 5.00 | 6.000000 7.000000 8.000000 9.000000 10.00"
        print("Tokenizing sequence...")
        tokens = tok(sequence_text, return_tensors="pt")
        print("Tokens:")
        print(tokens)
        
    except Exception as exc:
        print(f"FAILED: {exc}")

if __name__ == "__main__":
    test_tok()
