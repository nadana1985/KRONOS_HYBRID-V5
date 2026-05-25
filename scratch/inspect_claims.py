import sys
import os
import pandas as pd
import numpy as np

# Add local paths
sys.path.insert(0, os.path.abspath('.'))

from load_sovereign_config import load_sovereign_config
import neural_integration_engine
import feature_builder_engine

def run_diagnostics():
    config = load_sovereign_config('params_yaml.txt')

    print('--- CLAIM 1: MODEL LOAD ---')
    full_cfg = {
        'kronos_mini': config['kronos_mini'],
        'feature_builder': {'gate': config['feature_builder']['gate'], 'use_gpu': False},
        'reproducibility': config['reproducibility']
    }

    model = None
    tokenizer = None

    try:
        model = neural_integration_engine.load_verified_model(full_cfg)
        if model is None:
            print('FAILED: Model returned None.')
        else:
            print('SUCCESS: Model loaded.')
    except Exception as e:
        print(f'ERROR loading model: {e}')

    try:
        tokenizer = neural_integration_engine.load_verified_tokenizer(full_cfg)
        if tokenizer is None:
            print('FAILED: Tokenizer returned None.')
        else:
            print('SUCCESS: Tokenizer loaded.')
    except Exception as e:
        print(f'ERROR loading tokenizer: {e}')

    print('\n--- CLAIM 2: CONVICTION MULTIPLIER ---')
    if model and tokenizer:
        # Generate some dummy data
        np.random.seed(42)
        dates = pd.date_range('2020-01-01', periods=100, freq='5min')
        df = pd.DataFrame({
            'open': np.random.randn(100).cumsum() + 100,
            'high': np.random.randn(100).cumsum() + 101,
            'low': np.random.randn(100).cumsum() + 99,
            'close': np.random.randn(100).cumsum() + 100.5,
            'volume': np.random.rand(100) * 100
        }, index=dates)

        convictions = []
        for i in range(50, 100):
            emb = neural_integration_engine.extract_embeddings(df, i, model, tokenizer, full_cfg)
            conv = neural_integration_engine.compute_lp_norm(emb, full_cfg)
            convictions.append(conv)
        
        convictions = pd.Series(convictions)
        print(f'Conviction Stats: Mean={convictions.mean():.4f}, Std={convictions.std():.4f}')
        print(f'Median={convictions.median():.4f}, Max={convictions.max():.4f}, Min={convictions.min():.4f}')
        
        multiplier = config['feature_builder']['gate']['conviction_multiplier']
        threshold = convictions.median() * multiplier
        print(f'Threshold (median * {multiplier}) without vol_factor: {threshold:.4f}')
        passed = (convictions > threshold).sum()
        print(f'Number of bars passing without vol_factor: {passed} / {len(convictions)}')
    else:
        print('Skipping conviction test because model failed to load.')

if __name__ == '__main__':
    run_diagnostics()
