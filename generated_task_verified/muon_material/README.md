# Research Materials

Materials read during the Muon-on-CIFAR-10 reproduction.

## Index

| File | Source | What it is | Read on |
|------|--------|-----------|---------|
| `muon-blogpost.html` | https://kellerjordan.github.io/posts/muon/ | The Muon paper itself (blog form, by Keller Jordan) | 2026-06-15 |
| `muon-repo-README.md` | https://github.com/KellerJordan/Muon | Official Muon repo README — usage, examples, citations | 2026-06-15 |
| `muon-repo-muon.py` | https://github.com/KellerJordan/Muon/blob/master/muon.py | Reference Muon implementation (distributed + single-device) | 2026-06-15 |
| `cifar10-airbench94_muon.py` | https://github.com/KellerJordan/cifar10-airbench | The paper's CIFAR-10 example using Muon — CifarNet, 8 epochs, 94% | 2026-06-15 |
| `jeremybernstein-muon-derivation.html` | https://jeremybernste.in/writing/deriving-muon | Jeremy Bernstein's theoretical derivation of Muon (referenced in repo README) | 2026-06-15 |

## Notes

- The paper has no arXiv PDF — it lives only as the kellerjordan blog post.
- Bernstein's derivation is a deeper theoretical complement (signSGD/Shampoo dual view).
- The official `muon.py` includes a distributed `Muon` (with `dist.all_gather`) and a `SingleDeviceMuon`; my reproduction in `../code/muon.py` follows the single-device version.
- The airbench script is *not* what we re-ran — its 8-epoch / 94% target relies on tricks (whitening layer, batch 2000, TTA, specialized init) that fall outside the scope of a standard reproduction. We used a standard SmallCNN + 50 epochs to make the optimizer comparison clean.
