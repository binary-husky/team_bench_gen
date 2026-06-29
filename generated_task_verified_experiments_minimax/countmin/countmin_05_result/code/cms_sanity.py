"""Quick sanity test with smaller parameters."""
import numpy as np
from cms_experiment import run_one_seed

# Quick sanity check
pe, fe, F1, F2, F2h = run_one_seed(42)
print(f"\nSanity check (seed=42): point_err={pe:.6e}, F2_err={fe:.6e}")
print(f"  F1={F1}, F2={F2:.3e}, F2_hat={F2h:.3e}")
